#!/bin/bash

# Directory containing images
IMAGE_DIR="./original"

# Create an output directory if it doesn't exist
OUTPUT_DIR="."
mkdir -p "$OUTPUT_DIR"

# Loop through all images in the directory
for IMAGE in "$IMAGE_DIR"/*.{jpg,jpeg,png}; do
    # Get the dimensions of the image
    WIDTH=$(identify -format "%w" "$IMAGE")
    HEIGHT=$(identify -format "%h" "$IMAGE")

    # Determine the smallest dimension for square cropping
    MIN_DIM=$(($WIDTH<$HEIGHT ? $WIDTH : $HEIGHT))

    # If either dimension is less than 640, skip resizing
    if [ "$WIDTH" -lt 640 ] || [ "$HEIGHT" -lt 640 ]; then
        echo "Skipping $IMAGE because it is smaller than 640px."
        cp "$IMAGE" "$OUTPUT_DIR/"
        continue
    fi

    # Crop the image to a square in the middle, then resize it
    echo "Processing $IMAGE..."
    convert "$IMAGE" -gravity center -crop "${MIN_DIM}x${MIN_DIM}+0+0" +repage -resize 640x640 "$OUTPUT_DIR/$(basename "$IMAGE")"
done

echo "Processing complete. Resized images are in $OUTPUT_DIR."

