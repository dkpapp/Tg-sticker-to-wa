#```python
import os
import tempfile
import zipfile
import subprocess
from PIL import Image

async def process_sticker_pack(stickers_chunk, pack_title, part_num, total_parts, bot):
    """
    Downloads stickers, converts them to exactly 512x512 WebP formats, 
    and packages them into a .wastickers zip archive.
    """
    temp_dir = tempfile.mkdtemp()
    wastickers_filename = f"{pack_title}_Vol{part_num}.wastickers".replace(" ", "_")
    wastickers_path = os.path.join(tempfile.gettempdir(), wastickers_filename)
    
    skipped_tgs = 0
    processed_files = []
    cover_image_path = None

    try:
        # Create Title and Author text files required by Sticker Maker
        with open(os.path.join(temp_dir, 'title.txt'), 'w', encoding='utf-8') as f:
            suffix = f" {part_num}" if total_parts > 1 else ""
            f.write(f"{pack_title}{suffix}")
            
        with open(os.path.join(temp_dir, 'author.txt'), 'w', encoding='utf-8') as f:
            f.write("Tg2Wa Bot")

        for index, sticker in enumerate(stickers_chunk):
            if sticker.is_animated:
                # .tgs formats are gzipped lottie files requiring extensive C++ binaries to parse reliably.
                skipped_tgs += 1
                continue

            # Download the raw sticker file from Telegram
            tg_file = await bot.get_file(sticker.file_id)
            _, ext = os.path.splitext(tg_file.file_path)
            raw_path = os.path.join(temp_dir, f"raw_{index}{ext}")
            await tg_file.download_to_drive(raw_path)

            webp_path = os.path.join(temp_dir, f"{index + 1}.webp")

            if sticker.is_video:
                # Convert .webm to .webp using ffmpeg
                convert_webm_to_webp(raw_path, webp_path)
            else:
                # Convert/Resize static image using Pillow
                convert_static_to_webp(raw_path, webp_path)

            if os.path.exists(webp_path):
                processed_files.append(webp_path)
                
                # Generate a 96x96 tray/cover icon from the very first valid sticker
                if not cover_image_path:
                    cover_image_path = os.path.join(temp_dir, 'tray.png')
                    create_tray_icon(webp_path, cover_image_path)

        # If no valid stickers were processed (e.g. all were TGS), abort pack creation
        if not processed_files:
            return None, skipped_tgs

        # Fallback cover if generation failed
        if not cover_image_path or not os.path.exists(cover_image_path):
            cover_image_path = os.path.join(temp_dir, 'tray.png')
            Image.new('RGBA', (96, 96), (255, 255, 255, 0)).save(cover_image_path, 'PNG')

        # Zip it all up into a .wastickers file
        with zipfile.ZipFile(wastickers_path, 'w') as zf:
            zf.write(os.path.join(temp_dir, 'title.txt'), arcname='title.txt')
            zf.write(os.path.join(temp_dir, 'author.txt'), arcname='author.txt')
            zf.write(cover_image_path, arcname='tray.png')
            
            for file_path in processed_files:
                # Add to zip root natively
                zf.write(file_path, arcname=os.path.basename(file_path))

        return wastickers_path, skipped_tgs

    finally:
        # Cleanup temporary files
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(temp_dir)

def convert_static_to_webp(input_path, output_path):
    """Resizes a static image to exactly 512x512 while keeping aspect ratio padded."""
    try:
        img = Image.open(input_path).convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)
        
        # Create a blank 512x512 transparent canvas
        background = Image.new('RGBA', (512, 512), (255, 255, 255, 0))
        
        # Paste the resized image into the center
        bg_w, bg_h = background.size
        img_w, img_h = img.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        
        background.paste(img, offset)
        background.save(output_path, 'WEBP')
    except Exception as e:
        print(f"Error converting image to WEBP: {e}")

def create_tray_icon(input_path, output_path):
    """Creates a 96x96 tray icon required for the pack."""
    try:
        img = Image.open(input_path).convert("RGBA")
        img.thumbnail((96, 96), Image.Resampling.LANCZOS)
        
        background = Image.new('RGBA', (96, 96), (255, 255, 255, 0))
        bg_w, bg_h = background.size
        img_w, img_h = img.size
        offset = ((bg_w - img_w) // 2, (bg_h - img_h) // 2)
        
        background.paste(img, offset)
        background.save(output_path, 'PNG')
    except Exception as e:
        print(f"Error creating tray icon: {e}")

def convert_webm_to_webp(input_path, output_path):
    """Uses ffmpeg to convert a WebM video sticker to an animated WebP for WhatsApp."""
    # Note: Requires ffmpeg installed on the host system.
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-vcodec", "libwebp",
        # Force scale to 512x512 with transparent padding
        "-vf", "scale='if(gt(a,1),512,-1)':'if(gt(a,1),-1,512)',pad=512:512:(ow-iw)/2:(oh-ih)/2:color=black@0",
        "-lossless", "0", "-compression_level", "4",
        "-q:v", "50", "-loop", "0",
        output_path
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except FileNotFoundError:
        print("FFMPEG is not installed on the system. Video stickers will fail.")
    except Exception as e:
        print(f"FFMPEG conversion failed: {e}")
