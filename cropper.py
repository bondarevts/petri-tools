from __future__ import annotations
from pathlib import Path

import cv2 as cv
import numpy as np
from typing import Tuple

SCANNER_PLATE_RADIUS = 1044 // 2


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


def crop_plates(path: Path, output_folder: Path) -> None:
    scanner_image = cv.imread(str(path))
    gray = cv.cvtColor(scanner_image, cv.COLOR_BGR2GRAY)
    blur = cv.GaussianBlur(gray, ksize=(5, 5), sigmaX=0)
    canny = cv.Canny(blur, threshold1=60, threshold2=120)
    circle_centers = cv.HoughCircles(
        canny, cv.HOUGH_GRADIENT, dp=2, minDist=900, minRadius=480, maxRadius=540)[0, :, :2]
    for i, center in enumerate(sorted_plate_centers(circle_centers.astype(int))):
        print(path.stem, i)
        plate = cut_plate(scanner_image, center)
        cv.imwrite(str(output_folder / f'{path.stem}-{i + 1}{path.suffix}'), plate)


def main() -> None:
    for plate in Path('data/Gal5FOA_2020-08-17/').glob('*.tif'):
        crop_plates(plate, Path('data/Gal5FOA_2020-08-17-cropped/'))


if __name__ == '__main__':
    main()
