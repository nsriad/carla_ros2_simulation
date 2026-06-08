#!/usr/bin/env python3
import os
from PIL import Image

def main():
    images_dir = '../data/processed_camera/images'
    output_gif = '../data/processed_camera/simulation_preview.gif'
    
    # get and sort frame list
    frames = [f for f in os.listdir(images_dir) if f.endswith('.png')]
    frames.sort()
    
    # define slice (5s at 100fps)
    start_idx = 0000
    end_idx = 1000
    
    # to downsample to 25fps: frames[start_idx:end_idx:4]
    selected_frames = frames[start_idx:end_idx:4]
    
    print(f"Loading {len(selected_frames)} frames to generate GIF...")
    
    # load and resize frames
    image_list = []
    for frame_name in selected_frames:
        frame_path = os.path.join(images_dir, frame_name)
        img = Image.open(frame_path)
        
        # resize for lightweight output
        img = img.resize((img.width // 2, img.height // 2), Image.Resampling.LANCZOS)
        image_list.append(img)
        
    # compile animated gif
    print("Compiling GIF, this may take a moment...")
    
    # save the first frame and append the rest
    image_list[0].save(
        output_gif,
        save_all=True,
        append_images=image_list[1:],
        duration=40,
        loop=0
    )
    
    print(f"Success! GIF saved to: {output_gif}")

if __name__ == '__main__':
    main()
