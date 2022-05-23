#!/usr/bin/env python3
"""
A script to extract text out of low resolution screenshots from classic 
DOS games. 

Inputs: 
 - a set of character images 
 - a screenshot / subsection of screenshot

This repository contains example character images and a screenshot for the 
game Colonization from Sid Meier (1994).

Two aproaches are implemented. 
 - Exact pixel matching: we loop over all coordinates in the screenshot and, at each coordinate, try
   matching all of the character images pixel-by-pixel. If multiple character images match, use the one
   with the maximum size and advance by the width of that char. 100% accuracy!
 - Sliding-window template matching: a sliding window of the maximum size of the 
   character images runs over the screenshot. In each window, all of the character
   images are matched using the opencv template matching function. The one with 
   the best match (least deviation) is taken, and the sliding window as advanced
   by the width of the matching char. 99% accuracy.


Example:
 python3 extract-text-with-image-pixel-matching.py -s img/opening_003.png --ystart 194 img/char_* >stats.txt

For other games:
 - Take screenshots and extract all character images like the one provided here. Files should be named
   "char_[REPORTED CHAR].png", e.g. "char_8.png" will later be printed as "8"
 - adapt char_name_translations in this code to match your filenames
 - play around with ystart, yend coordinates 

Credits:
 - https://stackoverflow.com/questions/67826760/how-to-detect-if-an-image-is-in-another-image

Requirements:
  - python 3.6+
  - opencv


Author: Mario Fasold
License: MIT

"""
import cv2
import time
import pathlib
import math
import argparse
import logging

char_name_translations = {
    "slash": "/",
    "separator2": " ",
    "separator3": " ",
    "separator": " ",
}


def sliding_window(image, window_size, step=1):
    """
    Slide a window through the image
    """
    for y in range(0, image.shape[0] - window_size[1], step):
        for x in range(0, image.shape[1] - window_size[0], step):
            yield (x, y, image[y : y + window_size[1], x : x + window_size[0]])


class ExtractTextWithPixelMatching:
    def get_best_image_match_above_theshold(self, img, treshold=10e-8):
        """
        Detect if img contains one of the defined characters, and return the best match, i.e.
        the one which a) maches the pixels above a given treshold and b) has the maximum size
        among the considered chars
        """
        best_score = 0
        best_char = None

        for char_name, template_img in self.possible_chars:
            # Template matching using TM_SQDIFF: Perfect match => minimum value around 0.0
            result = cv2.matchTemplate(img, template_img, cv2.TM_SQDIFF)

            # Get value of best match, i.e. the minimum value
            min_val = cv2.minMaxLoc(result)[0]
            score = img.size - min_val  # make sure that among same-sized image the best one is selected

            if min_val <= treshold and score > best_score:
                best_score = score
                best_char = char_name, template_img

        return best_char

    def extract_text_with_template_matching(self, large_img, window_size):
        """
        Extracts text using sliding-window template matching: a sliding window of the maximum size of the
        character images runs over the screenshot. In each window, all of the character
        images are matched using the opencv template matching function. The one with
        the best match (least deviation) is taken, and the sliding window as advanced
        by the width of the matching char. 99% accuracy.
        """
        final_text = ""
        window_iter = sliding_window(large_img, window_size, 1)
        while True:
            try:
                x, y, window = next(window_iter)
            except StopIteration:
                break

            best_image = self.get_best_image_match_above_theshold(window)
            if best_image:
                char_name, template_img = best_image
                logging.info(f"Template {char_name} found at {x},{y}")
                final_text += char_name

                # advance by size of char
                # @todo: this would not work if step !=1
                for _ in range(template_img.shape[1] - 1):
                    next(window_iter)
        return final_text

    def extract_text_with_exact_matching(self, large_img, max_char_size):
        """
        We loop over all coordinates in the screenshot and, at each coordinate, try
        matching all of the character images pixel-by-pixel. If multiple character images
        match, use the one with the maximum size and advance by the width of that char.
        """
        final_text = ""
        x, y = (0, 0)
        while y < large_img.shape[0] - max_char_size[1]:
            while x < large_img.shape[1] - max_char_size[0]:
                # check which of the chars match at the current position
                logging.debug(f"Checking coordinate {x},{y}")
                matching_chars = []
                for char_name, img in self.possible_chars:
                    # check if ALL pixels match
                    if (large_img[y : y + img.shape[0], x : x + img.shape[1]] == img).all():
                        logging.info(f"Template {char_name} found at {x},{y}")
                        matching_chars.append((char_name, img, img.size))

                # pick the largest one
                if matching_chars:
                    largest_char = max(matching_chars, key=lambda l: l[2])  # some lambda funcion in shape[]
                    final_text += largest_char[0]
                    x += largest_char[1].shape[1]
                else:
                    x += 1
            y += 1
        return final_text

    def remove_consecutive_duplicate_seperators(self, text, sep=","):
        """
        Some chars (e.g. spaces) might be detected many times, but should be reported only once
        """
        deduplicated = text[0] if text else ""
        for c in text[1:]:
            if c in sep and c == deduplicated[-1]:
                continue
            else:
                deduplicated += c
        return deduplicated

    def extract_text(self, screenshot_file, char_image_files, method, y_start=0, y_end=None):
        """
        Main method that loads screenshot, character images, and runs the selected method 
        """
        # Import large image
        large_img = cv2.imread(str(screenshot_file))
        large_img = large_img[
            y_start:y_end,
        ] 
        if logging.DEBUG >= logging.root.level: 
            cv2.imshow("Full image", large_img)
            cv2.waitKey(0)

        # Import chars
        char_images = []
        max_char_size = (0, 0)
        for f in char_image_files:
            char_name = f.stem[5:]
            for k in char_name_translations.keys():
                char_name = char_name.replace(k, char_name_translations[k])
            img = cv2.imread(str(f))
            char_images.append((char_name, img))
            if img.size > max_char_size[0] * max_char_size[1]:
                max_char_size = (img.shape[1], img.shape[0])
        self.possible_chars = char_images

        logging.info(f"Importet {len(char_images)} character images")
        logging.info(f"Maximum char size is {max_char_size}")

        # Extract text with sliding window & pixel-by-pixel matching
        if method == "template":
            final_text = self.extract_text_with_template_matching(large_img, window_size=max_char_size)
        else:
            final_text = self.extract_text_with_exact_matching(large_img, max_char_size=(3, 5))

        logging.info(f"Text before deduplication: {final_text}")
        cleaned_text = self.remove_consecutive_duplicate_seperators(final_text, " ")
        print(str(screenshot_file) + cleaned_text)

    def cli(self, cmd_args=None):
        """
        The commandline interface
        """
        parser = argparse.ArgumentParser(
            description="Extract text from classic game screenshots",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument("-v", "--verbose", action="count", default=1, help="Verbosity (-v, -vv, ...)")
        parser.add_argument(
            "char_images", nargs="+", type=pathlib.Path, help="List of images containing the chars to be extracted"
        )
        parser.add_argument(
            "-s",
            "--screenshot",
            dest="screenshot_file",
            type=pathlib.Path,
            required=True,
            help="The image file containing the screenshot (png, tif)",
        )
        parser.add_argument(
            "--matching-method", choices=["exact", "template"], default="exact", help="Extraction method"
        )
        parser.add_argument(
            "--ystart", type=int, help="Starting searching the screenshot at this y position", default=0
        )
        parser.add_argument("--yend", type=int, help="End searching the screenshot at this y position", default=None)

        args = parser.parse_args(cmd_args)

        args.verbose = 70 - (10 * args.verbose) if args.verbose > 0 else 0
        logging.basicConfig(level=args.verbose)

        self.extract_text(args.screenshot_file, args.char_images, args.matching_method, args.ystart, args.yend)


et = ExtractTextWithPixelMatching()
if __name__ == "__main__":
    et.cli()
