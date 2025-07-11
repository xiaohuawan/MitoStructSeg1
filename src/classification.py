import os
import shutil
import json
import time
from ultralytics import YOLO
from tqdm import tqdm
from scipy import ndimage
from PIL import Image
import numpy as np
import torch
import torchvision

print("PyTorch version:", torch.__version__)
print("Torchvision version:", torchvision.__version__)


class MitoClassify:
    def __init__(self, file_path=" ", model_path="") -> None:
        self.file_path = file_path
        self.model_path = model_path

        self.predicts_all = []
        self.class_all = []
        self.labeled_array = []
        self.cnt_all = []
        self.masks_all = []

    def handel(self, image_path, model_path):
        self.file_path = image_path
        self.model_path = model_path
        self.predict_cls()
        self.get_label()


    def predict_cls(self):
        try:
            picpath = self.file_path

            # Process the original .tif image and save it as .png
            if picpath.endswith('.tif'):
                original_image = Image.open(picpath)
                png_image_path = picpath.replace('.tif', '.png')
                original_image.save(png_image_path)
                picpath = png_image_path  # Update path to .png

            model = YOLO(self.model_path).to('cpu')
            results = model.predict(picpath)

            predict_all = []
            masks_all = []

            with tqdm(total=len(results), desc="PREDICTING", unit="images") as pbar:
                for result in results:
                    im_bgr = result.plot()
                    predict_all.append(im_bgr[..., ::-1])  # Swap channels from BGR to RGB
                    
                    masks = np.array(result.masks.data.cpu())  # Ensure masks tensor is on the CPU
                    mask_cls = result.boxes.cls.cpu().numpy()  # Ensure classification tensor is on the CPU
                    
                    mask_img = np.zeros((masks.shape[1], masks.shape[2]))
                    for index, m in enumerate(masks):
                        mask_img[m != 0] = 255 if mask_cls[index] == 1 else 127
                    masks_all.append(mask_img)
                    pbar.update()

            self.predicts_all = predict_all
            self.masks_all = masks_all
            
            # Print debugging information
            print(f"Finished prediction. Number of images: {len(self.predicts_all)}")
        except Exception as e:
            print(f"An error occurred during prediction: {e}")





    def get_label(self):
        masks_all = np.array(self.masks_all)
        labeled_array, num_features = ndimage.label(masks_all)
        self.labeled_array = labeled_array
        cnts = np.zeros(num_features + 1, dtype=int)

        with tqdm(total=np.prod(labeled_array.shape), desc="counting", unit="pixels") as pbar:
            for idx in np.ndindex(labeled_array.shape):
                cnts[labeled_array[idx]] += (1 if (masks_all[idx] == 255) else -1)
                pbar.update()

        cnt_all = np.zeros(2)
        for i in range(num_features):
            if (cnts[i + 1] > 0):
                cnt_all[1] += 1
            else:
                cnt_all[0] += 1

        self.class_all = np.where(cnts[1:] > 0, 1, 0)
        self.cnt_all = cnt_all

    def save_results(self, output_path):
        # Prepare directories
        current_path = os.getcwd()
        json_dir = os.path.abspath(os.path.join(current_path, '..', 'vite', 'public', 'class_predict'))
        labeled_array_dir = os.path.abspath(os.path.join(current_path, '..', 'vite', 'public', 'labeled_arrays'))
        print("8888888888888888", json_dir)

        # Ensure directories are created (without clearing)
        os.makedirs(labeled_array_dir, exist_ok=True)
        os.makedirs(json_dir, exist_ok=True)

        # Determine the base filename
        base_filename = os.path.basename(self.file_path).split('.')[0]
        
        # Save results to file
        with open(output_path, 'a') as f:
            label_array_path = os.path.join(labeled_array_dir, f"{base_filename}.npy")
            np.save(label_array_path, self.labeled_array)
            f.write(f"class_all: {self.class_all}\n")
            f.write(f"cnt_all: {self.cnt_all}\n")
            f.write("\n")
        print("Results saved successfully.")

        # Save predicted images and return paths
        image_paths = self.save_predicted_images(json_dir)
        
        return image_paths

    # def save_predicted_images(self, output_dir):
    #     print(f"Saving predicted images to {output_dir}")
    #     os.makedirs(output_dir, exist_ok=True)
    #     base_filename = os.path.basename(self.file_path).split('.')[0]
    #     timestamp = round(time.time() * 1000)  # Time in milliseconds

    #     image_paths = []
    #     for idx, predict in enumerate(self.predicts_all):
    #         img = Image.fromarray(predict)
    #         img_filename = f"{base_filename}.png"
    #         img_path = os.path.join(output_dir, img_filename)
            
    #         img.save(img_path)
    #         image_paths.append(img_path)
    #         print(f"Saved image: {img_path}")
        
        # return image_paths

    def save_predicted_images(self, output_dir):
        print(f"Saving predicted images to {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
        base_filename = os.path.basename(self.file_path).split('.')[0]
        timestamp = round(time.time() * 1000)  # Time in milliseconds

        image_paths = []
        for idx, predict in enumerate(self.predicts_all):
            img = Image.fromarray(predict)
            img_filename = f"{base_filename}.png"  # Ensure unique file name
            img_path = os.path.join(output_dir, img_filename)
            
            print(f"Attempting to save image: {img_path}")
            try:
                img.save(img_path)
                image_paths.append(img_path)
                print(f"Saved image to: {img_path}")
            except Exception as e:
                print(f"Error saving image {idx}: {e}")
        
        print(f"All predicted images have been attempted to be saved.")
        return image_paths



    def get_results(self, output_path):
        with open(output_path, 'r') as file:
            content = file.read()
        return content

    @staticmethod
    def move_images_and_save_paths(source_dir, target_directory, json_filename):
        print(f"Starting to move images from {source_dir} to {target_directory}")

        # Ensure target directory exists (without clearing)
        os.makedirs(target_directory, exist_ok=True)


        image_paths = []

        for filename in os.listdir(source_dir):
            source_path = os.path.join(source_dir, filename)
            
            if filename.lower().endswith(('.png')): 
                if filename.lower().endswith('.tif'):
                    print(f"Converting .tif file: {filename}")
                    img = Image.open(source_path)
                    filename = filename.replace('.tif', '.png')
                    target_path = os.path.join(target_directory, filename)
                    img.save(target_path)
                    print(f"Converted .tif to .png and saved: {target_path}")
                else:
                    target_path = os.path.join(target_directory, filename)
                    print(f"Moving {source_path} to {target_path}")
                    shutil.move(source_path, target_path)
                

                relative_path = os.path.join('../free/class_source', filename)
                image_paths.append(relative_path)

        json_path = os.path.join(target_directory, json_filename)
        with open(json_path, 'w') as json_file:
            json.dump(image_paths, json_file)
        print(f"Saved image paths to {json_path} ")

        return image_paths

    @staticmethod
    def update_image_paths(json_path, directory):
        # Get all image paths from the specified directory
        image_paths = []
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith('.png'):
                    image_paths.append(os.path.join('../free/class_predict', file))
                    # a = os.path.join('../free/class_predict', file)
                    # print("aaaaaaaaaaaa", a)

        # Save image paths to JSON file
        with open(json_path, 'w') as json_file:
            json.dump(image_paths, json_file, indent=4)


def run_classification(image_paths, model_path, task_id=None, progress_data=None):
    results = []

    # Initialize progress
    total_tasks = len(image_paths)
    if progress_data is not None:
        progress_data['progress'] = 0

    mito_cls = MitoClassify()

    current_path = os.getcwd()
    json_dir = os.path.abspath(os.path.join(current_path, '..', 'vite', 'public', 'class_predict'))
    labeled_array_dir = os.path.abspath(os.path.join(current_path, '..', 'vite', 'public', 'labeled_arrays'))
    target_directory = os.path.join(os.path.abspath('../vite/public/class_source'))
    for directory in [json_dir, labeled_array_dir, target_directory]:
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)
    print("Cleared existing data in target directories ")

    # Process each image
    for i, image_path in enumerate(image_paths):
        # Update progress display to show i/n
        print(f"Processing image {i + 1}/{total_tasks}: {image_path}")

        mito_cls.handel(image_path, model_path)

        base_filename = os.path.basename(image_path).split('.')[0]
        results_file_path = os.path.join(os.path.abspath('../vite/public/class_predict'), f"{base_filename}.txt")

        # Save results and get image paths
        image_paths = mito_cls.save_results(results_file_path)
        result = mito_cls.get_results(results_file_path)

        # Update results list
        results.append({
            'image': image_path,
            'result': result,
            'predicted_image_paths': image_paths
        })

        # Update progress
        if progress_data is not None:
            progress_data['progress'] = int((i + 1) / total_tasks * 100)

    MitoClassify.update_image_paths(os.path.join(os.path.abspath('../vite/public/class_predict'), 'image_paths.json'), os.path.abspath('../vite/public/class_predict'))
    source_directory = 'uploaded_files'
    target_directory = os.path.join(os.path.abspath('../vite/public/class_source'))
    json_filename = "class_source.json"
    MitoClassify.move_images_and_save_paths(source_directory, target_directory, json_filename)

    return results


if __name__ == "__main__":
    # Ensure the target directory exists
    source_directory = 'uploaded_files'
    target_directory = os.path.join(os.path.abspath('../vite/public/class_source'))
    # print("**********1", target_directory)
    json_filename = "class_source.json"

    # Execute function
    MitoClassify.move_images_and_save_paths(source_directory, target_directory, json_filename)

    print(f"Files in '{source_directory}': {os.listdir(source_directory)}")







