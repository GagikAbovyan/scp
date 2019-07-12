import pickle
import json
import cv2
import os
import numpy as np
import xml.etree.cElementTree as ET
import base64
import socket
import shutil
import pyrebase
import sys
import re
import tempfile
import io
# from flask_mail import Mail, Message
from xml.dom import minidom
from flask import Flask, jsonify, request, Response, render_template , send_from_directory, redirect, url_for, session
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit
# from gevent.pywsgi import WSGIServer
from PIL import Image
from StringIO import StringIO
from datetime import datetime, timedelta

STATIC_DIR = './'
TEMPLATE_DIR = './'

#read configs
with open('data.json') as f:
	data = json.load(f)
	STATIC_DIR = data['staticDir']
	TEMPLATE_DIR = data['templateDir']

config = {'apiKey': 'AIzaSyCFbQehxrjn8eSprAr8JmSwEZSREIQbiN4',
          'authDomain': 'puzl-84135.firebaseapp.com',
					'databaseURL': 'https://puzl-84135.firebaseio.com',
					'projectId': 'puzl-84135',
					'storageBucket': 'puzl-84135.appspot.com',
					'messagingSenderId': '6480789:web:a83caec25e8d012e'
					}
firebase = pyrebase.initialize_app(config)
auth = firebase.auth()
app = Flask(__name__, static_folder = STATIC_DIR, template_folder = TEMPLATE_DIR, static_url_path = '')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
socketio = SocketIO(app)
dirName = 'XMLs/'
users = {}
trackerTypes = ['BOOSTING', 'MIL', 'KCF','TLD', 'MEDIANFLOW', 'GOTURN', 'MOSSE', 'CSRT']
APP__ROOT = os.path.dirname(os.path.abspath(__file__))

#initialize user dict 
def initData(userKey):
	global users
	users[userKey] = {}
	users[userKey]['trackers'] = []
	users[userKey]['rects'] = []
	users[userKey]['classes'] = []
	users[userKey]['countXML'] = 1
	users[userKey]['count'] = 1
	users[userKey]['frameID'] = 1
	users[userKey]['videoName'] = ''
	users[userKey]['countFrames'] = 1
	users[userKey]['isInitTrackers'] = False
	createDir('./XMLs/' + userKey)

# home
@app.route('/', methods=['GET', 'POST'])
@cross_origin()
def home():
	# global alreadyChecked
	global users
	return render_template('index.html'),201, {'Access-Control-Allow-Origin': '*'}

# close tab
@app.route('/close', methods=['GET'])
@cross_origin()
def close():
	global users
	return 'close'

# login page users
@app.route('/login', methods=['GET', 'POST'])
@cross_origin()
def login():
	global users
	return render_template('index.html'),200, {'Access-Control-Allow-Origin': '*'}
 
# login users
@app.route('/sign-in', methods=['GET', 'POST'])
@cross_origin()
def signIn():
	global users
	# global alreadyChecked
	if request.method == 'POST':
		email = request.json['email']
		password = request.json['pass']
		try:
			user = auth.sign_in_with_email_and_password(email, password)
			# print(auth.send_email_verification(user['localId']))
			session.permanent = True
			return json.dumps({'success':True})
		except:
			print('error')
			return json.dumps({'success':False})
	else:
		return json.dumps({'success':False})

@app.route('/sign-out', methods=['GET'])
@cross_origin()
def signOut():
	session.permanent = False
	return redirect(url_for('login'))

# register users
@app.route('/register', methods=['GET', 'POST'])
def register():
	global users
	if request.method == 'POST':
		email = request.json['email']
		password = request.json['pass']
		try:
			auth.create_user_with_email_and_password(email, password)
			return json.dumps({'success':True})
		except:
			return json.dumps({'success':False})
	else:
		return json.dumps({'success':False})

# user page
@app.route('/user', methods=['GET', 'POST'])
@cross_origin()
def user():
	global users
	if session.permanent is True:
		return render_template('index.html'),200, {'Access-Control-Allow-Origin': '*'}
	else:
		return redirect(url_for('login'))


# track objects track
@app.route('/track',methods = ['POST'])
@cross_origin()
def data():
	global trackerTypes
	global users
	global dirName
	global count 
	innerClasses = []
	privKey = request.json['privKey']
	userKey = request.remote_addr + privKey
	url = request.json['data']['url']
	canvasWidth = request.json['data']['width']
	canvasHeihgt = request.json['data']['height']
	frame = readb64(url)
	# cv2.imwrite('./frame.png', frame)
	users[userKey]['frameID'] += 1
	bboxes = []
	if users[userKey]['count'] == 0:
		if users[userKey]['isInitTrackers'] == False:
			users[userKey]['trackers'] = []
		for val in users[userKey]['rects']:
			height, width, channels = frame.shape
			val['x'] = val['x'] * float(width) / canvasWidth
			val['y'] = val['y'] * float(height) / canvasHeihgt
			val['width'] = val['width'] * float(width) / canvasWidth
			val['height'] = val['height'] * float(height) / canvasHeihgt
			rect = (val['x'], val['y'], val['width'], val['height'])
			bboxes.append(rect)
		if users[userKey]['isInitTrackers'] == True:
			oldTrackerSize = len(users[userKey]['trackers'])
			for index in range(len(users[userKey]['trackers']), len(bboxes)):
				bbox = bboxes[index]
				users[userKey]['trackers'].append(createTrackerByName(trackerTypes[2]))
				users[userKey]['count'] += 1
			for i in range(oldTrackerSize, len(users[userKey]['trackers'])):
				users[userKey]['trackers'][i].init(frame, bboxes[i])
			users[userKey]['isInitTrackers'] = False
		else:		
			for bbox in bboxes:
				users[userKey]['trackers'].append(createTrackerByName(trackerTypes[2]))
				users[userKey]['count'] += 1
			for i in range(len(users[userKey]['trackers'])):
				users[userKey]['trackers'][i].init(frame, bboxes[i])	
	rectParam = []
	rectForReturn = []
	height, width, channels = frame.shape
	for i in range(len(users[userKey]['trackers'])):
		height, width, channels = frame.shape 
		success, box = users[userKey]['trackers'][i].update(frame)
		p1 = (int(box[0]), int(box[1]))
		p2 = (int(box[0]) + int(box[2]), int(box[1]) + int(box[3]))
		if success == True:
			rectParam.append(box)
		else:
			del users[userKey]['trackers'][i]
			del users[userKey]['classes'][i]
			del users[userKey]['rects'][i]
			break
	for rect in rectParam:
		rectForReturn.append((int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])))
	positiveRects = []
	for rect in rectForReturn:
		if rect[0] > 0:
			positiveRects.append(rect)
	for positive in positiveRects:
		counter = users[userKey]['countXML']
		filePath = dirName + userKey + '/' + users[userKey]['videoName'] + '/file' + str(counter) + '_ID-' + str(users[userKey]['frameID'])  + '.xml'
		fileName = 'image_' + str(users[userKey]['frameID']) + '.png'
		name = users[userKey]['classes'][rectForReturn.index(positive)]
		innerClasses.append(name)
		if positive[0] == positiveRects[0][0]:
			height, width = frame.shape[:2]
			writeXML(filePath, fileName, name, str(width), str(height), str(positive[0]), str(positive[1]), str(positive[2]), str(positive[3]))
		if positive[0] != positiveRects[0][0]:
			appendXML(filePath, name, str(positive[0]), str(positive[1]), str(positive[2]), str(positive[3]))
		if positive[0] == positiveRects[-1][0]:
			users[userKey]['countXML'] += 1
	for i in range(len(rectForReturn)):
		rect = rectForReturn[i]
		newX = float(rect[0]) * canvasWidth / float(width)
		newY = float(rect[1]) * canvasHeihgt / float(height)
		newWidth = float(rect[2]) * canvasWidth / float(width)
		newHeight = float(rect[3]) * canvasHeihgt / float(height)
		rect = (int(newX), int(newY), int(newWidth), int(newHeight))
		rectForReturn[i] = rect
	return json.dumps({'success':True, 'rects':rectForReturn, 'className':innerClasses})

# convert hevc videos
def convert_video(video_input, fileName):
	# commandForCast = 'ffmpeg -i ' + video_input + ' -c:v libx264 -preset slow -x265-params crf=22 -c:a libmp3lame -b:a 128k ' + STATIC_DIR + 'c' + fileName
	commandForFps = 'ffmpeg -i ' + video_input  + ' -c:v libx264 -preset medium -crf 22 -vf setpts=3*PTS -an '  + STATIC_DIR + 'c' + fileName
	# print(video_input)
	# cmds = ['ffmpeg', '-i', video_input, '-c:v', 'libx264', '-preset', 'slow', '-x265-params', 'crf=22', '-c:a' 'libmp3lame', '-b:a', '128k', video_output]
	# subprocess.Popen(cmds)
	# os.system(commandForCast)
	# os.system(commandForFps)
	commandForRemove = 'rm -f ' + STATIC_DIR  + fileName
	# os.system(commandForRemove)
	# os.system(commandForCast)
	os.system(commandForFps)
	os.system(commandForRemove)


#upload file /upload
@app.route('/upload', methods = ['GET', 'POST'])
@cross_origin()
def uploadFile():
	global dirName
	userKey = request.remote_addr + str(request.headers['privKey'])
	initData(userKey)
	try:
		file = request.files['file']
	except:
		file = None
	target = os.path.join(STATIC_DIR)
	if not os.path.isdir(target):
		os.mkdir(target)
	ext = os.path.splitext(file.filename)
	fileName = str(ext[0]) + '-' + datetime.now().strftime('%Y%m%d_%H%M%S') + ext[1]
	destination = '/'.join([target, fileName])
	file.save(destination)
	users[userKey]['rects'][:] = []
	users[userKey]['trackers'] = []
	users[userKey]['videoName'] = fileName
	users[userKey]['originalName'] = str(file.filename)
	# path = dirName + userKey + '/' + fileName
	# createDir(path)
	metaData = getVideoDetails(STATIC_DIR + fileName)
	# print subprocess.check_output(['ls','-l'])
	# if metaData['video']['codec'] != 'h264':
	convert_video(STATIC_DIR + fileName, fileName)
	users[userKey]['videoName'] = 'c' + fileName
	fileName = 'c' + fileName
	path = dirName + userKey + '/' + fileName
	createDir(path)
	# return json.dumps({'fileName':False})
	return json.dumps({'fileName':fileName, 'isCasted':True})
	# path = dirName + userKey + '/' + fileName
	# createDir(path)
	# return json.dumps({'fileName':fileName, 'isCasted':False})

#export files /export
@app.route('/export/<privKey>', methods = ['GET'])
@cross_origin()
def exportFiles(privKey):
	global users
	global STATIC_DIR
	userKey = request.remote_addr + privKey
	currentDir = dirName + userKey + '/' + users[userKey]['videoName']
	videoPath = STATIC_DIR + users[userKey]['videoName']
	cap = cv2.VideoCapture(videoPath)
	xmls = os.listdir(currentDir)
	framesID = []
	for xml in xmls:
		framesID.append(int(xml.split('-')[1].split('.')[0]))
	cap = cv2.VideoCapture(videoPath)
	count = 0
	# Read until video is completed
	while(cap.isOpened()):
		count +=1
		# Capture frame-by-frame
		ret, frame = cap.read()
		if ret == True:
			# Display the resulting frame
			if count in framesID:
				path = currentDir + '/' + 'image_' + str(count) + '.png'
				num_rows, num_cols = frame.shape[:2]
				rotation_matrix = cv2.getRotationMatrix2D((num_cols/2, num_rows/2), 0, 1)
				img_rotation = cv2.warpAffine(frame, rotation_matrix, (num_cols, num_rows))
				cv2.imwrite(path, img_rotation)
		else: 
			break
	cap.release()
	cv2.destroyAllWindows()
	zipName = users[userKey]['videoName']
	zipDir(STATIC_DIR + '/' + zipName, currentDir)
	return json.dumps({'zipLink':zipName})

#socket
@socketio.on('add-data')
@cross_origin()
def sendMessage(message):
	global users
	privKey = message[0]['privKey']
	userKey = request.remote_addr + privKey
	for mes in message:
		users[userKey]['classes'].append(mes['name'])
	if len(users[userKey]['trackers']) > 0:
		for i in range(len(message)):
			del message[i]['privKey']
			users[userKey]['rects'].append(message[i])
		users[userKey]['isInitTrackers'] = True
		users[userKey]['count'] = 0
		return json.dumps({'data':'ok'})
	del message[0]['privKey']
	users[userKey]['rects'] = message
	users[userKey]['count'] = 0
	return  json.dumps({'data':'ok'})

# get metadata
def getVideoDetails(filepath):
	tmpf = tempfile.NamedTemporaryFile()
	os.system("ffmpeg -i \"%s\" 2> %s" % (filepath, tmpf.name))
	lines = tmpf.readlines()
	tmpf.close()
	metadata = {}
	for l in lines:
		l = l.strip()
		if l.startswith('Duration'):
			metadata['duration'] = re.search('Duration: (.*?),', l).group(0).split(':',1)[1].strip(' ,')
			metadata['bitrate'] = re.search("bitrate: (\d+ kb/s)", l).group(0).split(':')[1].strip()
		if l.startswith('Stream #0:0'):
			metadata['video'] = {}
			metadata['video']['codec'], metadata['video']['profile'] = \
					[e.strip(' ,()') for e in re.search('Video: (.*? \(.*?\)),? ', l).group(0).split(':')[1].split('(')]
			metadata['video']['resolution'] = re.search('([1-9]\d+x\d+)', l).group(1)
			metadata['video']['bitrate'] = re.search('(\d+ kb/s)', l).group(1)
			metadata['video']['fps'] = re.search('(\d+ fps)', l).group(1)
		if l.startswith('Stream #0:1'):
			metadata['audio'] = {}
			metadata['audio']['codec'] = re.search('Audio: (.*?) ', l).group(1)
			metadata['audio']['frequency'] = re.search(', (.*? Hz),', l).group(1)
			metadata['audio']['bitrate'] = re.search(', (\d+ kb/s)', l).group(1)
	return metadata

# parse base64 data 
def readb64(base64_string):
	decoded = base64.b64decode(base64_string)
	pimg = Image.open(io.BytesIO(decoded))
	return cv2.cvtColor(np.array(pimg), cv2.COLOR_RGB2BGR)

#create dir by name
def createDir(dirName):
	if not os.path.exists(dirName):
		os.makedirs(dirName)

#zip dir by name
def zipDir(zipName, dirName):
	shutil.make_archive(zipName, 'zip', dirName)

#for create and write xml
def writeXML(filePath, fileName, className, width, height, xmin, ymin, xmax, ymax):
	root = ET.Element('anotation')
	ET.SubElement(root, 'folder').text = 'frames'
	ET.SubElement(root, 'filename').text = fileName
	ET.SubElement(root, 'path').text = 'path'
	source = ET.SubElement(root, 'source')
	ET.SubElement(source, 'database').text = 'Unknown'
	size = ET.SubElement(root, 'size')
	ET.SubElement(size, 'width').text = width 
	ET.SubElement(size, 'height').text = height
	ET.SubElement(size, 'depth').text = '1' 
	ET.SubElement(root, 'segmented').text = '1'
	objectXML = ET.SubElement(root, 'object')
	ET.SubElement(objectXML, 'name').text = className
	ET.SubElement(objectXML, 'pose').text = 'Unspecified'
	ET.SubElement(objectXML, 'truncated').text = '1'  
	ET.SubElement(objectXML, 'difficult').text = '1' 
	bndbox = ET.SubElement(objectXML, 'bndbox')
	ET.SubElement(bndbox, 'xmin').text = xmin
	ET.SubElement(bndbox, 'ymin').text = ymin
	ET.SubElement(bndbox, 'xmax').text = xmax
	ET.SubElement(bndbox, 'ymax').text = ymax
	tree = ET.ElementTree(root)
	tree.write(filePath)

#for append already created xml
def appendXML(fileName, className, xmin, ymin, xmax, ymax):
	tree = ET.parse(fileName)
	root = tree.getroot()
	objectXML = ET.SubElement(root, 'object')
	ET.SubElement(objectXML, 'name').text = className
	ET.SubElement(objectXML, 'pose').text = 'Unspecified'
	ET.SubElement(objectXML, 'truncated').text = '1'  
	ET.SubElement(objectXML, 'difficult').text = '1' 
	bndbox = ET.SubElement(objectXML, 'bndbox')
	ET.SubElement(bndbox, 'xmin').text = xmin
	ET.SubElement(bndbox, 'ymin').text = ymin
	ET.SubElement(bndbox, 'xmax').text = xmax
	ET.SubElement(bndbox, 'ymax').text = ymax
	tree = ET.ElementTree(root)
	tree.write(fileName)

#for crteate tracker by type
def createTrackerByName(trackerType):
	global trackerTypes
	global multiTracker
	# Create a tracker based on tracker name
	if trackerType == trackerTypes[0]:
		tracker = cv2.TrackerBoosting_create()
	elif trackerType == trackerTypes[1]: 
		tracker = cv2.TrackerMIL_create()
	elif trackerType == trackerTypes[2]:
		tracker = cv2.TrackerKCF_create()
	elif trackerType == trackerTypes[3]:
		tracker = cv2.TrackerTLD_create()
	elif trackerType == trackerTypes[4]:
		tracker = cv2.TrackerMedianFlow_create()
	elif trackerType == trackerTypes[5]:
		tracker = cv2.TrackerGOTURN_create()
	elif trackerType == trackerTypes[6]:
		tracker = cv2.TrackerMOSSE_create()
	elif trackerType == trackerTypes[7]:
		tracker = cv2.TrackerCSRT_create()
	else:
		tracker = None
	return tracker

if __name__ == '__main__':
	createDir('.XMLs')	
	app.secret_key = 'OCML3BRawWEUeaxcuKHLpw'
	#app.run(threaded=True, debug=True, ssl_context=('cert.pem', 'privkey.pem'), host='annotations-tool.instigatemobile.com', port=443) 
	#http_server = WSGIServer(('annotations-tool.instigatemobile.com', 443), app, keyfile='privkey.pem', certfile='cert.pem')       
	#http_server.serve_forever()
	# app.run(debug=True, threaded=True, host='172.20.16.59', port=7000)
	#socketio.run(app, host='annotations-tool.instigatemobile.com', port=443, keyfile='privkey.pem', certfile='cert.pem')
	socketio.run(app, host='annotations-tool.instigatemobile.com', port=443, keyfile='privkey.pem', certfile='cert.pem')

