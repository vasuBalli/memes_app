import yt_dlp
import os

def download_instagram_video(url, output_folder="downloads"):
    # Ensure folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Configure yt-dlp
    ydl_opts = {
        'outtmpl': os.path.join(output_folder, '%(title)s.%(ext)s'),  # Save using post title
        'format': 'best',
        'quiet': False,
        'merge_output_format': 'mp4',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        print(f"✅ Downloaded: {filename}")
        return filename
download_instagram_video("https://www.instagram.com/reel/DM_nyswyNgs/?utm_source=ig_web_copy_link&igsh=MWFlYWg3dnJjajBraQ==")
