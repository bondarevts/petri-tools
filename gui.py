import enum
from pathlib import Path
from typing import List
from typing import Optional

import PySimpleGUI as sg
import cv2 as cv

import cropper

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}


class Key(enum.Enum):
    folder = 'folder'
    file_list = 'file list'
    width = 'width'
    height = 'height'
    show_preview = 'show preview'
    crop_selected = 'crop selected'
    crop_all = 'crop all'
    image = 'image'
    preview = 'preview'


def create_layout():
    left_column = [
        [
            sg.Text('Folder'),
            sg.InputText(size=(25, 1), enable_events=True, key=Key.folder),
            sg.FolderBrowse(initial_folder=Path('~').expanduser()),
        ],
        [
            sg.Listbox(
                values=[],
                select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                enable_events=True, size=(40, 20),
                key=Key.file_list,
            )
        ],
        [
            sg.Text('Set max width'),
            sg.InputText('400', key=Key.width, size=(5, 1)),
            sg.Text('and height'),
            sg.InputText('800', key=Key.height, size=(5, 1)),
        ],
        [sg.Checkbox('Show preview', key=Key.show_preview, enable_events=True)],
        [
            sg.Button('Crop all', key=Key.crop_all),
            sg.Button('Crop selected', key=Key.crop_selected)
        ],
    ]
    image_column = [
        [sg.Text('Initial image')],
        [sg.Image(key=Key.image)],
    ]
    preview_column = [
        [sg.Text('Output preview')],
        [sg.Image(key=Key.preview)]
    ]

    return [[
        sg.Column(left_column, element_justification='c'),
        sg.VSeperator(),
        sg.Column(image_column, element_justification='c'),
        sg.Column(preview_column, element_justification='c', justification='center'),
    ]]


def path_to_png_bytes(path: Path, max_size=None):
    image = cv.imread(path.as_posix())
    return image_to_png_bytes(image, max_size)


def image_to_png_bytes(image, scale):
    if scale != 1:
        image = resize_image(image, scale)
    _, buffer = cv.imencode(".png", image)
    return buffer.tobytes()


def calculate_scale(values, image):
    height, width = image.shape[:2]
    max_width, max_height = max_size(values)
    return min(max_height / height, max_width / width)


def resize_image(image, scale):
    height, width = image.shape[:2]
    interpolation = cv.INTER_AREA if scale < 1 else cv.INTER_LINEAR
    return cv.resize(image, (int(width * scale), int(height * scale)), interpolation=interpolation)


def max_size(values):
    if values[Key.width] and values[Key.height]:
        return int(values[Key.width]), int(values[Key.height])
    return None


def selected_files(values) -> List[Path]:
    return [Path(values[Key.folder]) / file_name for file_name in values[Key.file_list]]


def with_preview(values):
    return values[Key.show_preview]


def process_events(window):
    event, values = window.read()
    print(event)
    if event == sg.WINDOW_CLOSED:
        return False

    if event == Key.folder:
        process_folder_update(values, window)
        return True

    if event == Key.file_list:
        process_selection_update(values, window)
        return True

    if event == Key.show_preview:
        process_selection_update(values, window)
        return True

    if event == Key.crop_selected:
        return True

    return True


def process_folder_update(values, window):
    folder = Path(values[Key.folder])
    file_list = sorted(folder.iterdir())
    file_names = [f.name for f in file_list if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
    window[Key.file_list].update(file_names)


def process_selection_update(values, window):
    selected = selected_files(values)
    if not selected:
        update_image(window, image=None)
        update_preview(window, image=None)
        return

    if len(selected) > 1:
        return

    assert len(selected) == 1
    path = selected[0]

    if with_preview(values):
        show_image_with_cropping_preview(window, values, path)
    else:
        show_image(window, values, path)


def get_scaled_image(values, image, scale=None):
    if scale is None:
        scale = calculate_scale(values, image)
    return image_to_png_bytes(image, scale)


def show_image(window, values, path):
    image = cv.imread(path.as_posix())
    update_image(window, get_scaled_image(values, image))
    update_preview(window, image=None)


def show_image_with_cropping_preview(window, values, path):
    image = cv.imread(path.as_posix())
    scale = calculate_scale(values, image)

    centers = cropper.detect_plate_circles(image)
    plates = cropper.crop_plates(image, centers)
    cropper.draw_plate_circles(image, centers)
    update_image(window, get_scaled_image(values, image, scale))

    combined_image = cropper.combine_plates(plates, shape=cropper.get_combined_shape(centers))
    update_preview(window, get_scaled_image(values, combined_image, scale))


def update_image(window, image: Optional[bytes]):
    window[Key.image].update(data=image)


def update_preview(window, image: Optional[bytes]):
    window[Key.preview].update(data=image)


def main() -> None:
    window = sg.Window('Image Viewer', create_layout())

    while process_events(window):
        pass

    window.close()


if __name__ == '__main__':
    main()


# todo show numbers over found plates
# todo two ways of saving: separate plates and combined