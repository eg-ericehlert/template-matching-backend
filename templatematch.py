# templatematch.py
import boto3
import os
import numpy as np
import cv2 as cv
import csv
import logging
import matplotlib
matplotlib.use('Agg')  # Non-GUI backend
import matplotlib.pyplot as plt

# Set up logging
typical_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=typical_format)

# Predefined bright colors for annotations
BRIGHT_COLORS = [
    [0, 255, 0],      # Bright Green
    [255, 0, 0],      # Bright Red
    [128, 0, 128],    # Bright Purple
    [255, 165, 0],    # Bright Orange
    [255, 255, 0],    # Bright Yellow
    [0, 0, 255]       # Bright Blue
]

def download_image_from_s3(bucket_name, object_key, local_path):
    """
    Download an image from S3 bucket to a local path.
    """
    
    s3 = boto3.client('s3')
    try:
        s3.download_file(bucket_name, object_key, local_path)
        logging.info(f"Downloaded {object_key} from bucket {bucket_name} to {local_path}")
    except Exception as e:
        logging.error(f"Failed to download {object_key} from bucket {bucket_name}: {e}")

def apply_threshold(image, threshold_value=127):
    _, binary_image = cv.threshold(image, threshold_value, 255, cv.THRESH_BINARY)
    return binary_image

def rotate_image_90(image):
    return cv.rotate(image, cv.ROTATE_90_CLOCKWISE)

def rotate_image_180(image):
    return cv.rotate(image, cv.ROTATE_180)

def rotate_image_270(image):
    return cv.rotate(image, cv.ROTATE_90_COUNTERCLOCKWISE)

def flip_image(image):
    return cv.flip(image, 1)

def process_template_matching(img_gray_thresh, template_thresh, matching_threshold, template_name=None):
    """
    Run template matching with multiple transformations and return raw boxes and scores.
    """
    boxes = []
    scores = []
    transformations = [lambda x: x, flip_image, rotate_image_90, rotate_image_180, rotate_image_270]

    for transform in transformations:
        transformed = transform(template_thresh)
        res = cv.matchTemplate(img_gray_thresh, transformed, cv.TM_CCORR_NORMED)
        w, h = transformed.shape[::-1]
        loc = np.where(res >= matching_threshold)
        for pt in zip(*loc[::-1]):
            boxes.append([int(pt[0]), int(pt[1]), int(pt[0] + w), int(pt[1] + h)])
            scores.append(float(res[pt[::-1]]))

    return boxes, scores

def non_max_suppression(boxes, scores, overlap_thresh):
    """
    Perform non-maximum suppression and return indices of kept boxes.
    """
    if len(boxes) == 0:
        return []

    boxes_arr = np.array(boxes, dtype=float)
    scores_arr = np.array(scores)

    x1 = boxes_arr[:,0]
    y1 = boxes_arr[:,1]
    x2 = boxes_arr[:,2]
    y2 = boxes_arr[:,3]
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(scores_arr)

    pick = []
    while len(idxs) > 0:
        last = idxs[-1]
        pick.append(last)
        idxs = idxs[:-1]

        if len(idxs) == 0:
            break

        xx1 = np.maximum(x1[last], x1[idxs])
        yy1 = np.maximum(y1[last], y1[idxs])
        xx2 = np.minimum(x2[last], x2[idxs])
        yy2 = np.minimum(y2[last], y2[idxs])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        overlap = (w * h) / area[idxs]

        idxs = idxs[overlap <= overlap_thresh]

    return pick

def read_thresholds(csv_path):
    """
    Read a CSV of template thresholds with header ['template','threshold'].
    """
    thresholds = {}
    with open(csv_path, mode='r', newline='') as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) >= 2:
                thresholds[row[0]] = float(row[1])
    return thresholds

def run_job(input_dir, base_filename, nms_thresh=0.5):
    """
    Process the input image and templates, save annotated results, and return a summary dict.
    """
    # Paths
    main_path      = os.path.join(input_dir, base_filename)
    threshold_csv  = os.path.join(input_dir, 'thresholds.csv')
    template_folder= os.path.join(input_dir, 'templates')

    # Load main image
    img_rgb = cv.imread(main_path)
    if img_rgb is None:
        raise FileNotFoundError(f"Input image not found: {main_path}")
    logging.info(f"Loaded main image: {main_path}")

    # Preprocess
    img_gray = cv.cvtColor(img_rgb, cv.COLOR_BGR2GRAY)
    img_gray_thresh = apply_threshold(img_gray)

    # Read thresholds
    thresholds = read_thresholds(threshold_csv)
    logging.info(f"Loaded thresholds for {len(thresholds)} templates.")

    all_boxes, all_scores, all_names = [], [], []
    template_colors = {}
    color_idx = 0

    # Iterate templates
    for tpl_file in os.listdir(template_folder):
        tpl_path = os.path.join(template_folder, tpl_file)
        tpl = cv.imread(tpl_path, cv.IMREAD_GRAYSCALE)
        if tpl is None:
            logging.warning(f"Skipping unreadable template: {tpl_path}")
            continue

        # Assign color
        template_colors[tpl_file] = BRIGHT_COLORS[color_idx % len(BRIGHT_COLORS)]
        color_idx += 1

        tpl_thresh = apply_threshold(tpl)
        thresh_val = thresholds.get(tpl_file, 0.90)
        logging.info(f"Matching template {tpl_file} at threshold {thresh_val}.")

        boxes, scores = process_template_matching(img_gray_thresh, tpl_thresh, thresh_val)
        all_boxes.extend(boxes)
        all_scores.extend(scores)
        all_names.extend([tpl_file] * len(boxes))

    # Apply NMS
    keep_idxs = non_max_suppression(all_boxes, all_scores, nms_thresh) if all_boxes else []

    counts = {}
    for idx in keep_idxs:
        x1, y1, x2, y2 = all_boxes[idx]
        name = all_names[idx]
        color = template_colors[name]
        cv.rectangle(img_rgb, (x1, y1), (x2, y2), color, 3)
        counts[name] = counts.get(name, 0) + 1

    # Save annotated image
    results_img = os.path.join(input_dir, 'results.png')
    cv.imwrite(results_img, img_rgb)
    logging.info(f"Saved annotated image: {results_img}")

    # Plot counts without GUI
    counts_img = os.path.join(input_dir, 'annotation_counts.png')
    plt.figure(figsize=(10, 6))
    bar_colors = [tuple([v/255.0 for v in c]) for c in template_colors.values()]
    bars = plt.bar(counts.keys(), counts.values(), color=bar_colors)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    for bar in bars:
        plt.annotate(f"{int(bar.get_height())}",
                     xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                     xytext=(0, 3), textcoords="offset points", ha='center')
    plt.savefig(counts_img)
    plt.close()
    logging.info(f"Saved annotation counts graph: {counts_img}")

    return {
        "results_image": results_img,
        "counts_image": counts_img,
        "counts": counts
    }