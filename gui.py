import enum
from pathlib import Path
from threading import Thread
from typing import List
from typing import Optional

import PySimpleGUI as sg
import cv2 as cv

import cropper

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}
WAITING_GIF = sg.DEFAULT_BASE64_LOADING_GIF
WAITING_FRAMES_DELAY_MS = 100


class Key(enum.Enum):
    folder = 'folder'
    output_folder = 'output folder'
    file_list = 'file list'
    width = 'width'
    height = 'height'
    show_preview = 'show preview'
    crop_type = 'crop type'
    crop_selected = 'crop selected'
    crop_all = 'crop all'
    image = 'image'
    preview = 'preview'
    waiting_animation = 'waiting_animation'


class CropType(enum.Enum):
    separate = 'Crop as separate files'
    combined = 'Crop into combined images'


def create_layout():
    left_column = [
        [
            sg.Text('Folder', size=(10, 1)),
            sg.InputText(enable_events=True, key=Key.folder),
            sg.FolderBrowse(initial_folder=Path('~').expanduser()),
        ],
        [
            sg.Listbox(
                values=[],
                select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                enable_events=True, size=(65, 20),
                key=Key.file_list,
            )
        ],
        [
            sg.Text('Set preview image max width'),
            sg.InputText('400', key=Key.width, size=(5, 1)),
            sg.Text('and height'),
            sg.InputText('800', key=Key.height, size=(5, 1)),
        ],
        [
            sg.Text('Output folder', size=(10, 1)),
            sg.InputText(Path('~').expanduser(), key=Key.output_folder),
            sg.FolderBrowse(initial_folder=Path('~').expanduser())
        ],
        [
            sg.Checkbox('Show preview', key=Key.show_preview, enable_events=True),
            sg.InputOptionMenu([CropType.separate.value, CropType.combined.value], key=Key.crop_type),
            sg.Button('Crop selected', key=Key.crop_selected),
            sg.Button('Crop all', key=Key.crop_all),
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
        sg.Column(left_column, element_justification='l', vertical_alignment='top'),
        sg.VSeperator(),
        sg.Column(image_column, element_justification='c', vertical_alignment='top'),
        sg.Column(preview_column, element_justification='c', vertical_alignment='top'),
    ]]


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


def save_separately(values):
    return values[Key.crop_type] == CropType.separate.value


def output_folder(values):
    return Path(values[Key.output_folder])


def process_crop_selected(values):
    process_files(values, selected_files(values))


def process_crop_all(values):
    process_files(values, folder_files(values))


def process_files(values, files):
    action = cropper._save_separate_plates if save_separately(values) else cropper._save_combined_plates
    output = output_folder(values)
    total_files_to_process = len(files)
    if total_files_to_process == 0:
        return

    output.mkdir(exist_ok=True, parents=True)
    for i, f in enumerate(files):
        if not sg.OneLineProgressMeter('Cropping progress', i + 1, total_files_to_process, orientation='h'):
            return
        cropper.process_path(f, output, action)


def process_folder_update(values, window):
    window[Key.file_list].update([f.name for f in folder_files(values)])
    window[Key.output_folder].update(Path(values[Key.folder]) / 'cropped')
    update_image(window, image=None)
    update_preview(window, image=None)


def folder_files(values):
    folder = Path(values[Key.folder])
    try:
        files = sorted(folder.iterdir())
    except OSError:
        files = []
    return [
        f for f in files
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]


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
    def make_preview():
        nonlocal image, combined_image, scale
        image = cv.imread(path.as_posix())
        scale = calculate_scale(values, image)

        centers = cropper.detect_plate_circles(image)
        plates = cropper.crop_plates(image, centers)
        cropper.draw_plate_circles(image, centers, with_numbers=True)
        combined_image = cropper.combine_plates(plates, shape=cropper.get_combined_shape(centers))

    image = combined_image = scale = None
    thread = Thread(target=make_preview, daemon=True)
    thread.start()

    waiting_window = sg.Window(
        'Processing...',
        [[sg.Image(data=WAITING_GIF, key=Key.waiting_animation)]],
    )
    while thread.is_alive():
        waiting_window.read(timeout=WAITING_FRAMES_DELAY_MS)
        waiting_window[Key.waiting_animation].update_animation(WAITING_GIF, WAITING_FRAMES_DELAY_MS)
    thread.join()
    waiting_window.close()

    update_image(window, get_scaled_image(values, image, scale))
    update_preview(window, get_scaled_image(values, combined_image, scale))


def update_image(window, image: Optional[bytes]):
    window[Key.image].update(data=image)


def update_preview(window, image: Optional[bytes]):
    window[Key.preview].update(data=image)


def process_events(window):
    event, values = window.read()
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
        process_crop_selected(values)
        return True

    if event == Key.crop_all:
        process_crop_all(values)
        return True

    return True


def main() -> None:
    window = sg.Window('Image Viewer', create_layout())

    while process_events(window):
        pass

    window.close()


if __name__ == '__main__':
    main()
