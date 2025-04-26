
import time

import numpy as np
import numpy.typing as npt
import sounddevice as sd



class AudioPlayer:
    def __enter__(self):
        self.stream = sd.OutputStream(samplerate=24000, channels=1, dtype=np.int16)
        self.stream.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.stream.stop()  # wait for the stream to finish
        self.stream.close()

    def add_audio(self, audio_data: npt.NDArray[np.int16]):
        self.stream.write(audio_data)
