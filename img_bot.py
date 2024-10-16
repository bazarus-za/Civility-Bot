import discord
from discord.ext import commands
import requests
import json
import base64
import time
import torch
import gc  # For garbage collection
import subprocess
import psutil

# Set up the bot with commands and intents
intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent
bot = commands.Bot(command_prefix='/', intents=intents)

# Function to start the web UI
def start_webui():
    try:
        print("Starting Stable Diffusion WebUI...")
        process = subprocess.Popen([r"D:\Games\SD\forge\run.bat"], shell=True, cwd=r"D:\Games\SD\forge")
        time.sleep(5)
        print("Stable Diffusion WebUI started.")
        return process
    except Exception as e:
        print(f"Error starting Stable Diffusion WebUI: {e}")
        return None

def wait_for_server():
    for attempt in range(10):  # Retry up to 10 times
        try:
            response = requests.get("http://127.0.0.1:7861/sdapi/v1/options")
            if response.status_code == 200:
                print("Stable Diffusion WebUI is ready.")
                return True
        except requests.ConnectionError:
            print("Waiting for Stable Diffusion WebUI to start...")
        time.sleep(3)
    return False

# Load checkpoint function
def load_model(checkpoint_name):
    payload = {
        "sd_model_checkpoint": checkpoint_name
    }
    load_response = requests.post("http://127.0.0.1:7861/sdapi/v1/options", json=payload)
    if load_response.status_code != 200:
        print(load_response.text)  # Log the error response for more context
        raise Exception(f"Failed to load model: {checkpoint_name}")
    print(f"Checkpoint {checkpoint_name} loaded successfully.")

# Track VRAM usage
def track_vram():
    print(f"VRAM Allocated: {torch.cuda.memory_allocated() / 1024**2:.2f} MB")
    print(f"VRAM Reserved: {torch.cuda.memory_reserved() / 1024**2:.2f} MB")

# Enhanced unload model function
def unload_model():
    print("Before unloading:")
    track_vram()

    # Unload the model via the Stable Diffusion API
    unload_response = requests.post("http://127.0.0.1:7861/sdapi/v1/unload-checkpoint")
    
    # Log the full response for debugging
    print(f"Unload Response: {unload_response.status_code}, {unload_response.text}")
    
    if unload_response.status_code != 200:
        raise Exception(f"Failed to unload model. Status code: {unload_response.status_code}, Response: {unload_response.text}")

    print("Model unloaded successfully.")
    
    # Clear the GPU memory
    torch.cuda.empty_cache()
    gc.collect()

    time.sleep(5)  # Wait to ensure memory clears out
    print("After unloading:")
    track_vram()

# Models mapping for user terms
MODEL_MAP = {
    'art': {
        'model': 'albedobaseXL_v20.safetensors',
        'steps': 30,
        'cfg_scale': 4,
        'width': 832,
        'height': 1216,
        'sampler': 'dpm_sde',
        'scheduler': 'karras'
    },
    'realistic': {
        'model': 'realityvisionSDXL_v20.safetensors',
        'steps': 30,
        'cfg_scale': 4,
        'width': 1216,
        'height': 832,
        'sampler': 'dpmpp_2m',
        'scheduler': 'karras'
    },
    'flux': {
        'model': 'flux1-dev-bnb-nf4.safetensors',
        'steps': 20,
        'cfg_scale': 1,
        'width': 1152,
        'height': 896,
        'sampler': 'Euler',
        'scheduler': 'simple'
    }
}

# API URL for Stable Diffusion
SD_API_URL = "http://127.0.0.1:7861/sdapi/v1/txt2img"

# Function to trigger Stable Diffusion image generation
async def generate_image(prompt, model_data, save_path="D:/AI"):
    payload = {
        "prompt": prompt,
        "steps": model_data['steps'],
        "cfg_scale": model_data['cfg_scale'],
        "width": model_data['width'],
        "height": model_data['height'],
        "sampler_index": model_data['sampler'],
        "scheduler": model_data['scheduler'],
        "model": model_data['model']
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(SD_API_URL, data=json.dumps(payload), headers=headers)

    if response.status_code == 200:
        # Extract the base64 image from the response
        image_data = response.json()["images"][0]
        image_bytes = base64.b64decode(image_data)

        # Save the image to the specified path
        image_filename = f"{save_path}/generated_image.png"
        with open(image_filename, "wb") as img_file:
            img_file.write(image_bytes)

        return image_filename
    else:
        raise Exception(f"Error generating image: {response.status_code}")
import psutil

def terminate_webui_process(process_name="python.exe"):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['name'] == process_name and "launch.py" in proc.info['cmdline']:
            try:
                print(f"Terminating WebUI process (PID {proc.info['pid']})...")
                proc.terminate()
                proc.wait(timeout=5)  # Wait for it to close
                print(f"Process (PID {proc.info['pid']}) terminated.")
            except psutil.NoSuchProcess:
                print("Process already terminated.")
            except psutil.TimeoutExpired:
                print("Forcing process kill.")
                proc.kill()
                print(f"Process (PID {proc.info['pid']}) forcefully killed.")

# Register slash command
@bot.tree.command(name="create", description="Generate an image using Stable Diffusion.")
async def create(interaction: discord.Interaction, model: str, *, prompt: str):
    model_type = model.lower()

    if model_type not in MODEL_MAP:
        await interaction.response.send_message("Invalid model type. Choose between 'art', 'realistic', or 'flux'.")
        return

    model_data = MODEL_MAP[model_type]

    # Acknowledge the interaction
    await interaction.response.defer(thinking=True)

    # Start the Stable Diffusion process
    webui_process = start_webui()  # Ensure that this function runs run.bat
    if not wait_for_server():  # Ensure server is up and running
        await interaction.followup.send("Failed to start the server.")
        return

    # Load the specified model
    load_model(model_data['model'])

    # Generate the image
    image_filename = await generate_image(prompt, model_data)

    # Send the image in Discord
    await interaction.followup.send(file=discord.File(image_filename))

    # Stop the webui process to release VRAM
    terminate_webui_process()  # Use this to kill the Stable Diffusion process

def terminate_webui_process(process_name="python.exe"):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        # Check if the process name matches and if it's the expected script
        if proc.info['name'] == process_name and "launch.py" in proc.info['cmdline']:
            try:
                print(f"Attempting to terminate Web UI process (PID {proc.info['pid']})...")
                proc.terminate()  # Attempt to terminate
                proc.wait(timeout=5)  # Wait for it to close
                print(f"Web UI process (PID {proc.info['pid']}) terminated successfully.")
            except psutil.NoSuchProcess:
                print("Process already terminated.")
            except psutil.TimeoutExpired:
                print("Process did not terminate in time. Force killing.")
                proc.kill()  # Force kill if it's still running
                print(f"Web UI process (PID {proc.info['pid']}) forcefully killed.")
            except Exception as e:
                print(f"Error terminating process (PID {proc.info['pid']}): {e}")

bot.run('DISCORD_TOKEN_PLACEHOLDER')  # Use the correct token for the bot
