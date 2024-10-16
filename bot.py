import requests
import discord
import re
import json
import subprocess
import time
import psutil
import torch
import base64
import gc  # For garbage collection
from discord.ext import commands
from utils import load_model, unload_model

intents = discord.Intents.default()
intents.message_content = True  # Enable the intent needed for message content

# Use commands.Bot to support both slash commands and message handling
bot = commands.Bot(command_prefix="!", intents=intents)

SD_API_URL = "http://127.0.0.1:7861/sdapi/v1/txt2img"  # API URL for Stable Diffusion

# Load the config file
with open("D:/bot_files/config.json", "r") as file:
    config = json.load(file)

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

# Function to start the Stable Diffusion web UI
def start_webui():
    try:
        # Adjust the path to your local installation
        process = subprocess.Popen([r"D:\Games\SD\forge\run.bat"], shell=True, cwd=r"D:\Games\SD\forge")
        time.sleep(5)  # Wait for the server to start
        return process
    except Exception as e:
        print(f"Error starting web UI: {e}")
        return None

# Function to wait for the web UI server to be ready
def wait_for_server():
    for attempt in range(10):  # Try 10 times
        try:
            response = requests.get("http://127.0.0.1:7861/sdapi/v1/options")
            if response.status_code == 200:
                print("Server is ready.")
                return True
        except requests.ConnectionError:
            print("Waiting for the server to start...")
        time.sleep(2)  # Wait before retrying
    print("Failed to connect to the server after several attempts.")
    return False

# Function to generate an image using the Stable Diffusion API
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

# Function to terminate the web UI process
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

# Function to format payload for Ooba Booga responses
def format_payload(message, selected_character="Jerk"):
    prompt_template = config["prompts"][selected_character]["prompt"]
    
    # Clean and format the message
    cleaned_message = message.content.replace("\n", " ").strip()
    
    # Substitute the cleaned message into the prompt
    prompt = prompt_template.format(cleaned_message=cleaned_message)
    
    # Prepare the payload to send to the API
    payload = {
        "prompt": prompt,
        "max_new_tokens": config["prompts"][selected_character]["max_new_tokens"],
        "temperature": config["prompts"][selected_character]["temperature"],
        "top_p": config["prompts"][selected_character]["top_p"],
        "repetition_penalty": config["prompts"][selected_character]["repetition_penalty"],
        "use_history": config["prompts"][selected_character]["use_history"]
    }
    
    return payload

# Function to handle text responses via Ooba Booga API
async def analyze_and_respond(message):
    selected_character = "Jerk"  # Hardcoded character for now

    # Load the model before processing the message
    try:
        load_model("llama2.11b.fimbulvetr-v2.gguf_v2.q4_k_m.gguf")
    except Exception as e:
        print(f"Error loading model: {e}")
        await message.channel.send("Failed to load model. Please check the model file.")
        return

    payload = format_payload(message, selected_character)

    try:
        response = requests.post('http://127.0.0.1:5000/v1/completions', json=payload, timeout=120)
        response.raise_for_status()

        response_data = response.json()
        response_text = response_data.get('choices', [{}])[0].get('text', '').strip()

        if response_text:
            # Remove any code blocks from the response
            response_text = re.sub(r'```[\s\S]*?```', '', response_text)
            # Remove any remaining backticks
            response_text = response_text.replace('`', '')
            await message.channel.send(response_text)
        else:
            await message.channel.send("I couldn't generate a response. Try asking something else.")

    except requests.exceptions.RequestException as e:
        print(f"Error contacting the model: {e}")
        await message.channel.send("I'm having trouble thinking right now. Try again later.")
    finally:
        unload_model()  # Ensure the model is unloaded in the end

# Slash command to generate images via Stable Diffusion
@bot.tree.command(name="create", description="Generate an image using Stable Diffusion.")
async def create(interaction: discord.Interaction, model: str, *, prompt: str):
    model_type = model.lower()

    if model_type not in MODEL_MAP:
        await interaction.response.send_message("Invalid model type. Choose between 'art', 'realistic', or 'flux'.")
        return

    await interaction.response.defer(thinking=True)  # Acknowledge the command

    try:
        webui_process = start_webui()
        if not wait_for_server():
            await interaction.followup.send("Failed to start the server.")
            return

        load_model(MODEL_MAP[model_type]['model'])
        image_filename = await generate_image(prompt, MODEL_MAP[model_type])

        await interaction.followup.send(file=discord.File(image_filename))
    except Exception as e:
        await interaction.followup.send(f"Failed to generate image: {e}")
        print(f"Error during image generation: {e}")  # Debugging
    finally:
        terminate_webui_process()

# Handle regular messages, especially when the bot is mentioned
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    print(f"Received message: {message.content}")  # Debugging line
    if bot.user in message.mentions:  # Check if bot is mentioned
        await analyze_and_respond(message)

bot.run('DISCORD_TOKEN_PLACEHOLDER')

