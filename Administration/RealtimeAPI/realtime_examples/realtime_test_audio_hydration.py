import asyncio, base64, json, openai
import gradio as gr
import numpy as np
from pathlib import Path
from openai import AsyncAzureOpenAI
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastrtc import (
    AdditionalOutputs,
    AsyncStreamHandler,
    Stream,
    wait_for_item,
    UIArgs
)
from gradio.utils import get_space
from dotenv import load_dotenv
import os

load_dotenv()

SAMPLE_RATE = 24000

AZURE_OPENAI_API_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
SESSION_CONFIG={
    "input_audio_transcription": {
      "model": "gpt-realtime"
    },
    "turn_detection": {
      "threshold": 0.4,
      "silence_duration_ms": 600,
      "type": "server_vad"
    },
    "instructions": "Your name is Amy. You're a helpful agent who responds initially with a clam British accent, but also can speak in any language as the user chooses to. Always start the conversation with a cheery hello",
    "voice": "shimmer",
    "modalities": ["text", "audio"] ## required to solicit the initial welcome message
    }

def on_open(ws):
    print("Connected to server.")

def on_message(ws, message):
    data = json.loads(message)
    print("Received event:", json.dumps(data, indent=2))

class OpenAIHandler(AsyncStreamHandler):
    def __init__(self) -> None:
        super().__init__(
            expected_layout="mono",
            output_sample_rate=SAMPLE_RATE,
            output_frame_size=480,  # In this example we choose 480 samples per frame.
            input_sample_rate=SAMPLE_RATE,
        )
        self.connection = None
        self.output_queue = asyncio.Queue()

    def copy(self):
        return OpenAIHandler()

    async def hydrate(self):
        #read file content
        with open("conversation_history.md", "r") as file:
            hydration_msg = file.read()
            
        await self.connection.conversation.item.create( # type: ignore
            item={
                "type": "message",
                "role": "system",
                "content": [{"type": "message", "text": hydration_msg}],
            }
        )
        await self.connection.response.create() # type: ignore

    async def start_up(self):
        """
        Establish a persistent realtime connection to the Azure OpenAI backend.
        The connection is configured for server‐side Voice Activity Detection.
        """
        self.client = openai.AsyncAzureOpenAI(
            azure_endpoint=AZURE_OPENAI_API_ENDPOINT,
            azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
        )
        # When using Azure OpenAI realtime (beta), set the model/deployment identifier
        async with self.client.realtime.connect(
            model=AZURE_OPENAI_DEPLOYMENT_NAME  # Replace with your deployed realtime model id on Azure OpenAI.
        ) as conn:
            # Configure the session to use server-based voice activity detection (VAD)
            await conn.session.update(session=SESSION_CONFIG) # type: ignore
            self.connection = conn

            # Uncomment the following line to send a welcome message to the assistant.
            await self.hydrate()

            async for event in self.connection:
                # Handle interruptions
                if event.type == "input_audio_buffer.speech_started":
                    self.clear_queue()
                if event.type == "conversation.item.input_audio_transcription.completed":
                    # This event signals that an input audio transcription is completed.
                    await self.output_queue.put(AdditionalOutputs(event))
                if event.type == "response.audio_transcript.done":
                    # This event signals that a response audio transcription is completed.
                    await self.output_queue.put(AdditionalOutputs(event))
                if event.type == "response.audio.delta":
                    # For incremental audio output events, decode the delta.
                    await self.output_queue.put(
                        (
                            self.output_sample_rate,
                            np.frombuffer(base64.b64decode(event.delta), dtype=np.int16).reshape(1, -1),
                        ),
                    )

    async def receive(self, frame: tuple[int, np.ndarray]) -> None:
        """
        Receives an audio frame from the stream and sends it into the realtime API.
        The audio data is encoded as Base64 before appending to the connection's input.
        """
        if not self.connection:
            return
        _, array = frame
        array = array.squeeze()
        # Encode audio as Base64 string
        audio_message = base64.b64encode(array.tobytes()).decode("utf-8")
        await self.connection.input_audio_buffer.append(audio=audio_message)  # type: ignore

    async def emit(self) -> tuple[int, np.ndarray] | AdditionalOutputs | None:
        """
        Waits for and returns the next output from the output queue.
        The output may be an audio chunk or an additional output such as transcription.
        """
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None: # type: ignore
        if self.connection:
            await self.connection.close()
            self.connection = None

def update_chatbot(chatbot: list[dict], content):
    """
    Append the completed transcription to the chatbot messages.
    """
    if content.type == "conversation.item.input_audio_transcription.completed":
        chatbot.append({"role": "user", "content": content.transcript})
    elif content.type == "response.audio_transcript.done":
        chatbot.append({"role": "assistant", "content": content.transcript})
    return chatbot


# Create the Gradio Chatbot component for displaying conversation messages.
ui_args: UIArgs = UIArgs(
    title="APIM ❤️ OpenAI - Contoso Assistant 🤖",
)
chatbot = gr.Chatbot(type="messages")
latest_message = gr.Textbox(type="text", visible=True)

# Instantiate the Stream object that uses the OpenAIHandler.
stream = Stream(
    OpenAIHandler(),
    mode="send-receive",
    modality="audio",
    additional_inputs=[chatbot],
    additional_outputs=[chatbot],
    additional_outputs_handler=update_chatbot,
    ui_args=ui_args,
)

if __name__ == "__main__":
    stream.ui.launch(server_port=7990)
