from __future__ import annotations
from pathlib import Path

import cv2 as cv
import numpy as np
from typing import Tuple

SCANNER_PLATE_RADIUS = 1044 // 2
RED_COLOR = (0, 0, 255)


def to_grayscale(image):
    return cv.cvtColor(image, cv.COLOR_BGR2GRAY)


def edge_detection(image):
    return cv.Canny(image, threshold1=60, threshold2=120)


def blur(size=5):
    def apply(image):
        return cv.GaussianBlur(image, ksize=(size, size), sigmaX=0)
    return apply


def find_circles(image):
    return cv.HoughCircles(
        image, cv.HOUGH_GRADIENT, dp=1.3, minDist=SCANNER_PLATE_RADIUS * 2 - 50, minRadius=480, maxRadius=540
    )


def get_circle_centers(circles):
    return circles[0, :, :2].astype(int)


def detect_plate_circles(image):
    cropping_pipeline = pipeline(
        to_grayscale,
        blur(3),
        edge_detection,
        find_circles,
        get_circle_centers,
    )
    return sorted_plate_centers(cropping_pipeline(image))


def clear_outside_plate(image: np.ndarray) -> np.ndarray:
    radius = SCANNER_PLATE_RADIUS
    mask = np.zeros_like(image)
    cv.circle(mask, (radius, radius), radius, color=(255, 255, 255), thickness=-1)
    result = image.copy()
    result[mask != 255] = 0
    return result


def cut_plate(image: np.ndarray, center: Tuple[int, int]) -> np.ndarray:
    x, y = center
    radius = SCANNER_PLATE_RADIUS
    plate = image[y - radius:y + radius, x - radius:x + radius]
    return clear_outside_plate(plate)


def sorted_plate_centers(centers: np.ndarray) -> np.ndarray:
    positions = coordinates_to_positions(centers)
    result_indices = np.lexsort((positions[:, 0], positions[:, 1]))
    return centers[result_indices]


def coordinates_to_positions(centers):
    return (centers - centers.min(axis=0) + SCANNER_PLATE_RADIUS) // (SCANNER_PLATE_RADIUS * 2)


def pipeline(*functions):
    def call(image):
        for function in functions:
            image = function(image)
        return image

    return call


def crop_plates(image, circle_centers):
    return [cut_plate(image, center) for center in circle_centers]


def get_combined_shape(circle_centers):
    positions = coordinates_to_positions(circle_centers)
    columns, rows = positions.max(0) + 1
    return rows, columns


def show_detected_plates(image):
    centers = detect_plate_circles(image)
    draw_plate_circles(image, centers)
    return image


def draw_plate_circles(image, centers):
    for center in centers:
        cv.circle(image, tuple(center), radius=SCANNER_PLATE_RADIUS, color=RED_COLOR, thickness=7)


def combine_plates(plates, shape):
    rows, columns = shape
    diameter = SCANNER_PLATE_RADIUS * 2
    final_image = np.zeros((rows * diameter, columns * diameter, 3)).astype('uint8')
    for i, plate in enumerate(plates):
        top = (i // columns) * diameter
        left = (i % columns) * diameter
        final_image[top: top + diameter, left: left + diameter, :] = plate
    return final_image


def save_combined_plates(output_folder, path, combined_image):
    cv.imwrite(str(output_folder / f'{path.stem}-cropped{path.suffix}'), combined_image)


def save_separate_plates(output_folder, path, plates):
    for i, plate in enumerate(plates):
        print(path.stem, i)
        cv.imwrite(str(output_folder / f'{path.stem}-{i + 1}{path.suffix}'), plate)


def process_path(path: Path, output_folder: Path, action) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    scanner_image = cv.imread(str(path))
    print(f'Processing {path.name}')

    plate_centers = detect_plate_circles(scanner_image)
    action(output_folder, path, scanner_image, plate_centers)


def _save_separate_plates(output_folder, path, image, centers):
    plates = crop_plates(image, centers)
    save_separate_plates(output_folder, path, plates)


def _save_combined_plates(output_folder, path, image, centers):
    plates = crop_plates(image, centers)
    shape = get_combined_shape(centers)
    save_combined_plates(output_folder, path, combine_plates(plates, shape))


def _mark_plates(output_folder, path, image, centers):
    draw_plate_circles(image, centers)
    cv.imwrite(str(output_folder / f'{path.stem}-circles{path.suffix}'), image)


def main() -> None:
    for plate in sorted(Path('cropper-hard-cases').glob('*.tif')):
        process_path(plate, Path('results/circles'), _mark_plates)


if __name__ == '__main__':
    main()


# todo test for number of found plates and for their centers
