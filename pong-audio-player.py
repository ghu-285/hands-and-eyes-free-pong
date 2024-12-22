"""
    # PONG PLAYER EXAMPLE

    HOW TO CONNECT TO HOST AS PLAYER 1
    > python3 pong-audio-player.py p1 --host_ip HOST_IP --host_port 5005 --player_ip YOUR_IP --player_port 5007

    HOW TO CONNECT TO HOST AS PLAYER 2
    > python3 pong-audio-player.py p2 --host_ip HOST_IP --host_port 5006 --player_ip YOUR_IP --player_port 5008

    about IP and ports: 127.0.0.1 means your own computer, change it to play across computer under the same network. port numbers are picked to avoid conflits.

    DEBUGGING:
    
    You can use keyboards to send command, such as "g 1" to start the game, see the end of this file

"""
#native imports
import time
from playsound import playsound
import argparse

from pythonosc import osc_server
from pythonosc import dispatcher
from pythonosc import udp_client

# threading so that listenting to speech would not block the whole program
import threading
# speech recognition (default using google, requiring internet)
import speech_recognition as sr

# pitch & volume detection
import aubio
import numpy as num
import pyaudio
import wave

from gtts import gTTS
from synthesizer import Player, Synthesizer, Waveform
from pysinewave import SineWave
import os


mode = ''
debug = False
quit = False
y_paddle = 225
game_started = 0
curr_level = "easy"

host_ip = "127.0.0.1"
host_port_1 = 5005 # you are player 1 if you talk to this port
host_port_2 = 5006
player_1_ip = "127.0.0.1"
player_2_ip = "127.0.0.1"
player_1_port = 5007
player_2_port = 5008

player_ip = "127.0.0.1"
player_port = 0
host_port = 0

if __name__ == '__main__' :

    parser = argparse.ArgumentParser(description='Program description')
    parser.add_argument('mode', help='host, player (ip & port required)')
    parser.add_argument('--host_ip', type=str, required=False)
    parser.add_argument('--host_port', type=int, required=False)
    parser.add_argument('--player_ip', type=str, required=False)
    parser.add_argument('--player_port', type=int, required=False)
    parser.add_argument('--debug', action='store_true', help='show debug info')
    args = parser.parse_args()
    print("> run as " + args.mode)
    mode = args.mode
    if (args.host_ip):
        host_ip = args.host_ip
    if (args.host_port):
        host_port = args.host_port
    if (args.player_ip):
        player_ip = args.player_ip
    if (args.player_port):
        player_port = args.player_port
    if (args.debug):
        debug = True

player = Player()
player.open_stream()
synthesizer = Synthesizer(osc1_waveform=Waveform.sine, osc1_volume=0.3, use_osc2=False)

# GAME INFO

# functions receiving messages from host
# TODO: add audio output so you know what's going on in the game

def say(m):
    try:
        message = gTTS(m, lang="en", slow=False)
        temp = f"{time.time()}.wav"
        message.save(temp)
        playsound(temp)
        os.remove(temp)
    except Exception as e:
        print(f"error in say: {e}")

def on_receive_game(address, *args):
    global game_started, curr_level
    state = int(args[0])
    game_started = state
    # 0: menu, 1: game starts
    if state == 0:
        print("> menu")
        say(f"current level is {curr_level}")
        playsound('menu.wav')
    elif state == 1:
        print("> game has started")

player_lock = threading.Lock()

def ball_pitch(x, y):
    global game_started
    if game_started != 1: 
        return
    
    try:
        # map y to pitch
        min_pitch = 200
        max_pitch = 800
        frequency = min_pitch + ((y / 450) * (max_pitch - min_pitch))

        # map x to panning
        pan = max(0.0, min(x / 800, 1.0))  
        left_volume = 1.0 - pan
        right_volume = pan

        # generate wave with panning
        wave = synthesizer.generate_constant_wave(frequency, 0.02) 
        if wave.ndim != 1 or len(wave) == 0:
            raise ValueError("generated wave is not valid")
        
        stereo_wave = num.stack([wave * left_volume, wave * right_volume], axis=1)

        with player_lock:
            player.play_wave(stereo_wave)
    except Exception as e:
        print(f"error in ball_pitch: {e}")

def on_receive_ball(address, *args):
    global game_started
    if game_started != 1: 
        return
    # print("> ball position: (" + str(args[0]) + ", " + str(args[1]) + ")")
    ball_pitch(args[0], args[1])

def on_receive_paddle(address, *args):
    # print("> paddle position: (" + str(args[0]) + ", " + str(args[1]) + ")")
    pass

def on_receive_hitpaddle(address, *args):
    # example sound
    if mode == 'p1' and args[0] == 1:
        playsound('your_paddle.wav')
    elif mode == 'p2' and args[0] == 2:
        playsound('your_paddle.wav')
    else:
        playsound('opp_paddle.wav')
    print(f"> ball hit paddle {args[0]}")

def on_receive_ballout(address, *args):
    if mode == 'p1' and args[0] == 1:
        print("> opponent scored")
    elif mode == 'p2' and args[0] == 2:
        print("> opponent scored")
    else:
        print("> you scored")
    # print("> ball went out on left/right side: " + str(args[0]) )

def on_receive_ballbounce(address, *args):
    bound = int(args[0])
    # ball bouncing down
    if bound == 1:  
        # print("> ball bouncing down")
        playsound('ball_ceiling_bounce.wav')
        # bounce_sound(220) 
    # ball bouncing up
    elif bound == 2:  
        # print("> ball bouncing up")
        playsound('ball_floor_bounce.wav')
        # bounce_sound(440)

def on_receive_scores(address, *args):
    global y_paddle
    print("> scores now: " + str(args[0]) + " vs. " + str(args[1]))
    say(f"score is now {args[0]} to {args[1]}")

def on_receive_level(address, *args):
    global curr_level
    level = int(args[0])
    if level == 1:
        print("> current level: easy")
        curr_level = "easy"
    elif level == 2:
        print("> current level: hard")
        curr_level = "hard"
    elif level == 3:
        print("> current level: insane")
        curr_level = "insane"

def on_receive_powerup(address, *args):
    # 1 - freeze p1
    # 2 - freeze p2
    # 3 - adds a big paddle to p1, not use
    # 4 - adds a big paddle to p2, not use
    powerups= {
        0: "no active powerups",
        1: "player 1 is frozen",
        2: "player 2 is frozen",
        3: "player 1 can activate big paddle",
        4: "player 2 can activate big paddle"
    }
    print(f"> powerup now: {powerups[args[0]]}")
    say(powerups[args[0]])

def on_receive_p1_bigpaddle(address, *args):
    print("> p1 has a big paddle now")
    # when p1 activates their big paddle
    if mode == 'p1':
        playsound('your_big_paddle.wav')
    else:
        playsound('opp_big_paddle.wav')

def on_receive_p2_bigpaddle(address, *args):
    print("> p2 has a big paddle now")
    # when p2 activates their big paddle
    if mode == 'p1':
        playsound('opp_big_paddle.wav')
    else:
        playsound('your_big_paddle.wav')

def on_receive_hi(address, *args):
    print("> opponent says hi!")
    playsound('opp_hi.wav')

dispatcher_player = dispatcher.Dispatcher()
dispatcher_player.map("/hi", on_receive_hi)
dispatcher_player.map("/game", on_receive_game)
dispatcher_player.map("/ball", on_receive_ball)
dispatcher_player.map("/paddle", on_receive_paddle)
dispatcher_player.map("/ballout", on_receive_ballout)
dispatcher_player.map("/ballbounce", on_receive_ballbounce)
dispatcher_player.map("/hitpaddle", on_receive_hitpaddle)
dispatcher_player.map("/scores", on_receive_scores)
dispatcher_player.map("/level", on_receive_level)
dispatcher_player.map("/powerup", on_receive_powerup)
dispatcher_player.map("/p1bigpaddle", on_receive_p1_bigpaddle)
dispatcher_player.map("/p2bigpaddle", on_receive_p2_bigpaddle)
# -------------------------------------#

# CONTROL

# TODO add your audio control so you can play the game eyes free and hands free! add function like "client.send_message()" to control the host game
# We provided two examples to use audio input, but you don't have to use these. You are welcome to use any other library/program, as long as it respects the OSC protocol from our host (which you cannot change)

# example 1: speech recognition functions using google api
# -------------------------------------#
def listen_to_speech():
    global quit
    global y_paddle

    while not quit:
        # obtain audio from the microphone
        r = sr.Recognizer()
            
        # recognize speech using Google Speech Recognition
        try:
            # for testing purposes, we're just using the default API key
            # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
            # instead of `r.recognize_google(audio)`
            with sr.Microphone() as source:
                print("[speech recognition] say something!")
                audio = r.listen(source)
            recog_results = r.recognize_google(audio)
            print("[speech recognition] recognized input: \"" + recog_results + "\"")

            # if recognizing quit and exit then exit the program
            if recog_results == "quit" or recog_results == "exit":
                quit = True
                print("> exiting the program")
                playsound('quit.wav')
                break
            # if recog_results == "play" or recog_results == "start":
                # client.send_message('/g', 1)
            elif recog_results == "connect":
                client.send_message('/connect', player_ip)
                playsound('connect.wav')
            elif recog_results == "hi" or recog_results == "hello":
                client.send_message('/hi', 0)
                print("> said hi to opponent")
                playsound('sayHi.wav')
            elif recog_results == "play" or recog_results == "start" or recog_results == "resume":
                client.send_message('/setgame', 1)
                print("> started game")
                playsound('play.wav')
            elif recog_results == "pause" or recog_results == "menu":
                client.send_message('/setgame', 0)
                print("> paused game")
                # playsound('pause.wav')
            elif recog_results == "easy":
                client.send_message('/setlevel', 1)
                print("> set level to easy")
                playsound('setEasy.wav')
            elif recog_results == "hard":
                client.send_message('/setlevel', 2)
                print("> set level to hard") 
                playsound('setHard.wav')
            elif recog_results == "insane":
                client.send_message('/setlevel', 3)
                print("> set level to insane")
                playsound('setInsane.wav') 
            elif recog_results == "big paddle" or recog_results == "use big paddle" or recog_results == "activate big paddle":
                client.send_message('/setbigpaddle', 0)
                print("> set big paddle")
                playsound('activateBigPaddle.wav')
            elif "set paddle to" in recog_results or "move paddle to" in recog_results or "shift paddle to" in recog_results:
                y_pos = re.search(r"\d+", recog_results)
                if y_pos:
                    y_paddle = int(y_pos.group())
                    if 0 <= y_paddle <= 450:
                        client.send_message('/setpaddle', y_paddle)
                        print(f"> set paddle to: {y_paddle}")
                        playsound('paddleMoved.wav')
                    else:
                        print("> invalid paddle position")
                        playsound('invalidPaddlePos.wav')
                else:
                    print("> no paddle position found")
                    playsound('noPaddlePos.wav')
            elif recog_results == "instructions":
                playsound('instructions.wav')
            
        except sr.UnknownValueError:
            print("[speech recognition] could not understand speech input")
        except sr.RequestError as e:
            print("[speech recognition] could not request results; {0}".format(e))

# -------------------------------------#

# example 2: pitch & volume detection
# -------------------------------------#
# PyAudio object.
p = pyaudio.PyAudio()
# Open stream.
stream = p.open(format=pyaudio.paFloat32,
    channels=1, rate=44100, input=True,
    frames_per_buffer=1024)
# Aubio's pitch detection.
pDetection = aubio.pitch("default", 2048,
    2048//2, 44100)
# Set unit.
pDetection.set_unit("Hz")
pDetection.set_silence(-40)

# pitch thresholds for controlling the paddle
HIGH_PITCH_THRESHOLD = 280  # move paddle up if pitch > 300 Hz
LOW_PITCH_THRESHOLD = 200   # move paddle down if pitch < 200 Hz


def sense_microphone():
    global quit, y_paddle, game_started
    global debug
    while not quit:
        if game_started != 1:
            time.sleep(0.1)
            continue

        data = stream.read(1024,exception_on_overflow=False)
        # samples = num.fromstring(data, dtype=aubio.float_type)
        samples = num.frombuffer(data, dtype=aubio.float_type)

        # Compute the pitch of the microphone input
        pitch = pDetection(samples)[0]
        # Compute the energy (volume) of the mic input
        volume = num.sum(samples**2)/len(samples)
        # Format the volume output so that at most
        # it has six decimal numbers.
        volume = "{:.6f}".format(volume)

        if pitch > 0:
            # move paddle up
            if pitch > HIGH_PITCH_THRESHOLD:
                y_paddle = max(0, y_paddle - 10)  
                client.send_message('/setpaddle', y_paddle)
                # print(f"paddle moved up: {y_paddle}")

            # move paddle down
            elif pitch < LOW_PITCH_THRESHOLD:
                y_paddle = min(450, y_paddle + 10) 
                client.send_message('/setpaddle', y_paddle)
                # print(f"paddle moved down: {y_paddle}")
        
        if quit:
            break

        # uncomment these lines if you want pitch or volume
        # if debug:
        #     print("pitch "+str(pitch)+" volume "+str(volume))
# -------------------------------------#


# speech recognition thread
# -------------------------------------#
# start a thread to listen to speech
speech_thread = threading.Thread(target=listen_to_speech, args=())
speech_thread.daemon = True
speech_thread.start()

# pitch & volume detection
# -------------------------------------#
# start a thread to detect pitch and volume
microphone_thread = threading.Thread(target=sense_microphone, args=())
microphone_thread.daemon = True
microphone_thread.start()


# -------------------------------------#

# Play some fun sounds?
# -------------------------------------#
def hit():
    playsound('hit.wav', False)

# def score():
#     playsound('score.wav', False) 

# -------------------------------------#

# OSC connection
# -------------------------------------#
# used to send messages to host
if mode == 'p1':
    host_port = host_port_1
if mode == 'p2':
    host_port = host_port_2

if (mode == 'p1') or (mode == 'p2'):
    client = udp_client.SimpleUDPClient(host_ip, host_port)
    print("> connected to server at "+host_ip+":"+str(host_port))

# OSC thread
# -------------------------------------#
# Player OSC port
if mode == 'p1':
    player_port = player_1_port
if mode == 'p2':
    player_port = player_2_port

player_server = osc_server.ThreadingOSCUDPServer((player_ip, player_port), dispatcher_player)
player_server_thread = threading.Thread(target=player_server.serve_forever)
player_server_thread.daemon = True
player_server_thread.start()
# -------------------------------------#
client.send_message("/connect", player_ip)

# MAIN LOOP
# manual input for debugging
# -------------------------------------#
while not quit:
    m = input("> send: ")
    cmd = m.split(' ')
    if len(cmd) == 2:
        client.send_message("/"+cmd[0], int(cmd[1]))
    if len(cmd) == 1:
        client.send_message("/"+cmd[0], 0)
    
    # this is how client send messages to server
    # send paddle position 200 (it should be between 0 - 450):
    # client.send_message('/p', 200)
    # set level to 3:
    # client.send_message('/l', 3)
    # start the game:
    # client.send_message('/g', 1)
    # pause the game:
    # client.send_message('/g', 0)
    # big paddle if received power up:
    # client.send_message('/b', 0)
