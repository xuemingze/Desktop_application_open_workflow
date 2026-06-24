import base64
import sys

# ── Hide console windows for all ffmpeg/ffprobe subprocesses on Windows ──
# pydub calls subprocess.Popen without CREATE_NO_WINDOW, causing windows to
# flash. We patch the Popen reference inside pydub.audio_segment.
if sys.platform == "win32":
    import subprocess
    import pydub.audio_segment

    _original_popen = pydub.audio_segment.subprocess.Popen

    class _HiddenPopen:
        """subprocess.Popen wrapper that forces CREATE_NO_WINDOW on Windows."""

        __slots__ = ("_popen",)

        def __init__(self, *args, creationflags=0, **kwargs):
            # Always add CREATE_NO_WINDOW; user-provided creationflags are ORed in
            kwargs["creationflags"] = creationflags | subprocess.CREATE_NO_WINDOW
            self._popen = _original_popen(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._popen, name)

        def __enter__(self):
            return self._popen.__enter__()

        def __exit__(self, *args):
            return self._popen.__exit__(*args)

    pydub.audio_segment.subprocess.Popen = _HiddenPopen

# ── imports that depend on the patch ──
from pydub import AudioSegment
from pydub.utils import make_chunks
from ..agent.output_types import Actions, DisplayText


def _get_volume_by_chunks(audio: AudioSegment, chunk_length_ms: int) -> list:
    """
    Calculate the normalized volume (RMS) for each chunk of the audio.
    """
    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]


def prepare_audio_payload(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
    forwarded: bool = False,
) -> dict[str, any]:
    """
    Prepares the audio payload for sending to a broadcast endpoint.
    If audio_path is None, returns a payload with audio=None for silent display.
    """
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()

    if not audio_path:
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions.to_dict() if actions else None,
            "forwarded": forwarded,
        }

    try:
        audio = AudioSegment.from_file(audio_path)
        audio_bytes = audio.export(format="wav").read()
    except Exception as e:
        raise ValueError(
            f"Error loading or converting generated audio file to wav file '{audio_path}': {e}"
        )
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    volumes = _get_volume_by_chunks(audio, chunk_length_ms)

    payload = {
        "type": "audio",
        "audio": audio_base64,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions.to_dict() if actions else None,
        "forwarded": forwarded,
    }

    return payload
