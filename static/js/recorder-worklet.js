// recorder-worklet.js

class RecorderProcessor extends AudioWorkletProcessor {
    constructor() {
      super();
    }
  
    process(inputs, outputs, parameters) {
      // inputs[0] to tablica kanałów, inputs[0][0] to Float32Array z próbkami mono
      const inputChannelData = inputs[0][0];
      if (inputChannelData) {
        // wysyłamy próbki do głównego wątku
        this.port.postMessage(inputChannelData);
      }
      // true, żeby procesor pozostał aktywny
      return true;
    }
  }
  
  registerProcessor('recorder-processor', RecorderProcessor);
  