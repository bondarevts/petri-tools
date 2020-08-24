from pathlib import Path

import PySimpleGUI as sg
import cv2 as cv

import cropper

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'}


def create_layout():
    left_column = [
        [
            sg.Text('Folder'),
            sg.In(size=(25, 1), enable_events=True, key='-FOLDER-'),
            sg.FolderBrowse(initial_folder=Path('~').expanduser()),
        ],
        [
            sg.Listbox(
                values=[],
                select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED,
                enable_events=True, size=(40, 20),
                key='-FILE LIST-',
            )
        ],
        [
            sg.Text('Set max width'),
            sg.In('400', key='-W-', size=(5, 1)),
            sg.Text('and height'),
            sg.In('800', key='-H-', size=(5, 1)),
        ],
        [sg.Button('Save cropped picture', key='-SAVE-')],
    ]
    image_column = [
        [sg.Text('Initial image')],
        [sg.Image(key='-IMAGE-')],
    ]
    preview_column = [
        [sg.Text('Output preview')],
        [sg.Image(key='-PREVIEW-')]
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


def calculate_scale(image, max_size):
    height, width = image.shape[:2]
    max_width, max_height = max_size
    return min(max_height / height, max_width / width)


def resize_image(image, scale):
    height, width = image.shape[:2]
    interpolation = cv.INTER_AREA if scale < 1 else cv.INTER_LINEAR
    return cv.resize(image, (int(width * scale), int(height * scale)), interpolation=interpolation)


def max_size(values):
    if values['-W-'] and values['-H-']:
        return int(values['-W-']), int(values['-H-'])
    return None


def selected_path(values) -> Path:
    return Path(values['-FOLDER-']) / values['-FILE LIST-'][0]


def main() -> None:
    window = sg.Window('Image Viewer', create_layout())

    while True:
        event, values = window.read()
        if event == 'Exit' or event == sg.WIN_CLOSED:
            break

        if event == '-FOLDER-':
            folder = Path(values['-FOLDER-'])
            file_list = sorted(folder.iterdir())
            file_names = [f.name for f in file_list if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS]
            window['-FILE LIST-'].update(file_names)

        elif event == '-FILE LIST-':
            if not values['-FILE LIST-']:
                window['-IMAGE-'].update(data=None)
                window['-PREVIEW-'].update(data=None)
                continue

            try:
                file_name = selected_path(values)
                size = max_size(values)

                image = cv.imread(file_name.as_posix())
                scale = calculate_scale(image, max_size=size)
                centers = cropper.detect_plate_circles(image)
                plates = cropper.crop_plates(image, centers)
                cropper.draw_plate_circles(image, centers)
                window['-IMAGE-'].update(data=image_to_png_bytes(image, scale))

                combined_image = cropper.combine_plates(plates, shape=cropper.get_combined_shape(centers))
                window['-PREVIEW-'].update(data=image_to_png_bytes(combined_image, scale))
            except Exception:
                import traceback
                traceback.print_exc()

        elif event == '-SAVE-':
            pass

    window.close()


if __name__ == '__main__':
    main()


# todo show numbers over found plates
# todo two ways of saving: separate plates and combined
# todo check box for preview
