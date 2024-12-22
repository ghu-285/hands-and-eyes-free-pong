import pyttsx3

def test_tts():
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)  # Adjust speech rate if needed
    engine.setProperty('volume', 1.0)  # Set max volume
    engine.say("This is a test message")
    engine.runAndWait()

test_tts()