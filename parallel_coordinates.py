""" Parallel coordinate renderer
	By: Jeremy Carson (jerdak@gmail.com)


"""
from Tkinter import *
import json
import copy
import argparse
import os

WIDTH = 1000			# Screen width
WIDTHPAD = 100          # Screen width padding
HEIGHT = 500			# Screen height
HEIGHTPAD = 100         # Screen height padding (unused
PARALLELWIDTH = 10      # Width of each parallel coordinate

graph = None				# THE graph
last_parallel = None		# Last parallel coordinate selected with left mouse
last_mouse_down = None		# Last left mouse down coordinate
curruent_mouse_down = None	# Current mouse down coordinate

parallels = []				# All parallel coordinates
line_chains = []			# All line chains

class Vec2(object):
	""" Simple 2D vector class
	"""
	def __init__(self,x=0.0,y=0.0):
		self.x = x
		self.y = y
	def __add__(self,other):
		return Vec2(self.x + other.x,self.y + other.y)
	def __sub__(self,other):
		return Vec2(self.x - other.x,self.y - other.y)
	def __mul__(self,other):
		return Vec2(self.x * other,self.y * other)
	def __div__(self,other):
		return Vec2(self.x / other,self.y / other)
	@property
	def length(self):
		return math.sqrt(self.x**2 + self.y**2)
	@property
	def mag(self):
		return self.length
	@property
	def sqr_length(self):
		return self.x**2 + self.y**2

	@staticmethod
	def distance(a,b):
		return math.sqrt((b.x - a.x)**2 + (b.y - a.y)**2)

	def __str__(self):
		return "%f,%f"%(self.x,self.y)

class LineChain(object):
	"""	LineChain class

		LineChain's represent groups of nodes (vertices), 1 for each
		parallel coordinate that create a contiguous line between 
		all coordinates.
	"""
	def __init__(self):
		self.starts = []
		self.params = []
		self.values = []

	def add_node(self,param,start,value):
		"""	Add a new node(vertex) to this line chain

			Nodes = [Position,Parallel Coordinate,Raw Value]

			Input
				param - Parallel coordinate this node belongs to
				start - Position of this node
				value - Raw value of this node (e.g. if age is 20, value = 20)
		"""
		self.params.append(param)
		self.starts.append(start)
		self.values.append(value)

	def in_range(self):
		""" Returns true IFF all raw node values are within each parallel
			coordinate's range limiter
		"""
		for index in range(0,len(self.starts)-1):
			if not (self.params[index].in_range(self.values[index]) and
				self.params[index+1].in_range(self.values[index+1])):
				return False
		return True

	@property
	def visible(self):
		return self.in_range()

	@property
	def lines(self):
		""" Line generator

			Creates line pairs (start,end) from nodes
		"""
		num = 0
		while num < len(self.params)-1:
			yield (self.starts[num],self.starts[num+1])
			num += 1

class Parallel(object):
	""" Parallel Coordinate class

		Handles all things parallel coordinate related.
	"""
	def __init__(self,width,height,name,position,rng):
		self.width = width
		self.height = height
		self.position = position
		self.name = name
		self.data_range = rng
		self.limit_range = copy.copy(rng)
		self.color = '#00441b'

	def in_range(self,v):
		"""	Returns true IFF v is in range limiters

			Input
				v - Some real value
		"""
		return(v >= self.limit_range.x and v <= self.limit_range.y)

	def contains(self,x,y):
		"""	Returns true IFF the coordinate contains x and y

			Bounds of the parallel coordinate are treated as
			bounding box.
		"""
		return (x >= self.position.x and x <= self.position.x + self.width and
				y >= self.position.y and y <= self.position.y + self.height)

	def domain(self,v):
		"""	Convert raw value in to a pixel coordinate

			Parallel coordinates occupy a position in pixel space.  Position
			along this pixel space is determined by finding the percent
			distance 'v' is along the actual Parallel coordinate data range
			and then finding the equivalent pixel length.

			Input
				v - Raw value
		"""
		return (v - self.data_range.x) / float(self.data_range.y - self.data_range.x) * self.height + self.position.y
	
	def inverse_domain(self,v):
		"""	Convert pixel coordinate to raw value

			Parallel coordinates occupy a position in pixel space.  Raw value
			is determined by inverting the `domain()` process above.  

			Input
				v - Pixel value
		"""
		return (v - self.position.y) / float(self.height) * float(self.data_range.y - self.data_range.x) + self.data_range.x

	@property
	def is_limited(self):
		return (self.data_range.x != self.limit_range.x or self.data_range.y != self.limit_range.y)



def draw_parallels():
	""" Draw parallel coordinates

		Also draws the rectangles for the range limiter
	""" 
	for p in parallels:
		x1 = p.position.x
		y1 = p.position.y
		x2 = p.position.x + p.width
		y2 = p.position.y + p.height
		graph.create_rectangle((x1, y1, x2, y2), fill=p.color)
		
		# Draw a second rectangle to denote range limiter
		if p.is_limited:
			x1 = p.position.x
			y1 = p.domain(p.limit_range.x)
			x2 = p.position.x + p.width
			y2 = p.domain(p.limit_range.y)
			graph.create_rectangle((x1, y1, x2, y2), fill='#66c2a4')	

def draw_line_chains(render_invisible=False):
	""" Draw line chains

		Lines are chained from one coordinate to another so that
		the entire chain can be hidden if a single point in that
		chain is outside its parallel coordinate range.
	"""
	for lc in line_chains:
		if lc.visible:
			for line in lc.lines:
				x1 = line[0].x
				y1 = line[0].y
				x2 = line[1].x
				y2 = line[1].y
				graph.create_line(x1,y1,x2,y2,fill='#41ae76')
		else:
			# rendering multiple colors causes hefty lag in TKinter
			if render_invisible:
				for line in lc.lines:
					x1 = line[0].x
					y1 = line[0].y
					x2 = line[1].x
					y2 = line[1].y
					graph.create_line(x1,y1,x2,y2,fill='#99d8c9')

def draw_range_info():
	"""	Draw parallel coordinate range information

		Coordinate header and footer contain the current allowable
		range values.  e.g. Age[20]->Age[40] means all ages between
		(20,40) are allowed
	"""
	if last_mouse_down:
		text_top = "%s [%f]"%(last_parallel.name,last_parallel.limit_range.x)
		text_bot = "%s [%f]"%(last_parallel.name,last_parallel.limit_range.y)
		shift = len(text_top)*2.4
		graph.create_text(last_parallel.position.x-shift,last_parallel.position.y-10,anchor=W,font="Purisa",text=text_top,fill='black')
		graph.create_text(last_parallel.position.x-shift,last_parallel.position.y+last_parallel.height+10,anchor=W,font="Purisa",text=text_bot,fill='black')
	else:
		for p in parallels:
			text_top = "%s [%f]"%(p.name,p.limit_range.x)
			text_bot = "%s [%f]"%(p.name,p.limit_range.y)
			shift = len(text_top)*2.4
			graph.create_text(p.position.x-shift,p.position.y-10,anchor=W,font="Purisa",text=text_top,fill='black')
			graph.create_text(p.position.x-shift,p.position.y+p.height+10,anchor=W,font="Purisa",text=text_bot,fill='black')

def draw():
	"""	Update draw Canvas

		Note:  Do not call this frequently lest ye be stricken
		with 'mad lag'
	"""
	graph.delete(ALL)

	draw_parallels()
	draw_line_chains()
	draw_range_info()

	graph.update()

def left_mouse_down(event):
	""" Handle left mouse down

		Checks for intersection with an existing parallel coordinate
	"""
	global last_parallel
	global last_mouse_down
	print "clicked down", event.x, event.y 
	for p in parallels:
		if p.contains(event.x,event.y):
			p.color = '#238b45'
			last_parallel = p
			last_mouse_down = Vec2(event.x,event.y)
	draw()

def reset(event):
	"""	Reset scene

		All range limiters return to their original values
	"""
	print "Resetting scene" 
	for p in parallels:
		p.limit_range = copy.copy(p.data_range)
	draw()

def left_mouse_move(event):
	""" Handle mouse movement when left mouse down
	"""
	if last_parallel:
		min_range = last_parallel.inverse_domain(last_mouse_down.y)
		max_range = last_parallel.inverse_domain(event.y)

		# handle opposite vertical direction
		if max_range < min_range:
			max_range,min_range = min_range,max_range

		# clamp range limiters to be in range [parallel.data_range.x,parallel.dat_range.y]
		max_range = max(min(max_range,last_parallel.data_range.y),last_parallel.data_range.x)
		min_range = max(min(min_range,last_parallel.data_range.y),last_parallel.data_range.x)

		last_parallel.limit_range.x = min_range
		last_parallel.limit_range.y = max_range

	draw()

def left_mouse_up(event):
	""" Handle left mouse button up
	"""
	global last_parallel
	global last_mouse_down
	if last_parallel:
		last_parallel.color = '#00441b'
	last_parallel = None
	last_mouse_down = None
	print "clicked up", event.x, event.y 
	draw()

def build_graph():
	""" Build main graph and hook events
	"""
	global graph
	root = Tk()
	root.resizable(True,False)
	root.title("Parallel Coordinates")

	x = (root.winfo_screenwidth() - WIDTH) / 2
	y = (root.winfo_screenheight() - HEIGHT) / 2
	root.geometry('%dx%d+%d+%d' % (WIDTH, HEIGHT, x, y))
	
	root.bind_all('<Escape>', lambda event: event.widget.quit())
	root.bind("<Button-1>",left_mouse_down)
	root.bind("<B1-Motion>",left_mouse_move)
	root.bind("<ButtonRelease-1>",left_mouse_up)
	root.bind("<Button-3>",reset)

	graph = Canvas(root, width=WIDTH, height=HEIGHT, background='#f7fcfd')
	graph.pack()
	draw()

def canvas_step_size(num_keys):
	"""	Extract the step size between parallel coordinates that best
		fits within the canvas region
	"""
	working_width = (WIDTH-WIDTHPAD*2.0)
	used_width = working_width / float( PARALLELWIDTH*num_keys )
	unused_width = working_width - used_width
	return (PARALLELWIDTH + unused_width/float(num_keys-1))


def load_csv(file_name):
	""" Load json data file
	"""
	global parallels
	global line_chains

	with open(file_name,'r') as f:
		keys = next(f).strip().split(',')
		step = canvas_step_size(len(keys))
		f.seek(0)
		
		# create parallel coordinates from key names (assumes json keys are equivalent for all 'rows')
		tmp = []
		for index,key in enumerate(keys): 
			tmp.append(Parallel(PARALLELWIDTH,400,key,Vec2(0,0),Vec2(float("inf"),-float("inf"))))
		
		# first pass over data to set ranges for each parallel coordinate
		# this must be done BEFORE any calls to `domain()` or `inverse_domain()`
		next(f) # skip first line (keys)
		for index,line in enumerate(f):
			line = line.strip()
			data = line.split(',')

			if len(data) != len(keys):
				print "Malformed line[%d]. Row item count must be equal to the number of column identifiers. (Column Count: %d)"%(index,line,len(keys))

			for data_index,value in enumerate(data):
				value = float(value)
				tmp[data_index].data_range.x = min(value,tmp[data_index].data_range.x)
				tmp[data_index].data_range.y = max(value,tmp[data_index].data_range.y)

		for p in tmp:
		 	p.limit_range = copy.deepcopy(p.data_range)
			
		parallels = tmp

		# iterate over all parallel coordinates and set their position in 2D space
		x = WIDTHPAD/2
		y = HEIGHTPAD/2
		for index,p in enumerate(parallels):
			p.position = Vec2(x,y)
			x += step

		f.seek(0)
		next(f) # skip first line, keys
		# last step, iterate back over data to create line chains
		for line in f:
			line = line.strip()
			data = line.split(',')
			
			last_ln = None
			lc = LineChain()
			for index in range(0,len(data)):
				v1 = float(data[index])
				x1 = parallels[index].position.x + parallels[index].width / 2.0
			 	y1 = parallels[index].domain(v1)
			 	vec1 = Vec2(x1,y1)
			 	lc.add_node(parallels[index],vec1,v1)
			line_chains.append(lc)

def load_json(file_name):
	""" Load json data file
	"""
	global parallels
	global line_chains
	with open(file_name,'r') as f:
		data = json.load(f)
		keys = data[0].keys()
		step = canvas_step_size(len(keys))
	
		# create parallel coordinates from key names (assumes json keys are equivalent for all 'rows')
		tmp = {}
		for index,key in enumerate(keys): 
			tmp[key] = Parallel(PARALLELWIDTH,400,key,Vec2(0,0),Vec2(float("inf"),-float("inf")))
		
		# first pass over data to set ranges for each parallel coordinate
		# this must be done BEFORE any calls to `domain()` or `inverse_domain()`
		for datum in data:
			for item in datum.items():
				key,value = item
				value = float(value)
				tmp[key].data_range.x = min(value,tmp[key].data_range.x)
				tmp[key].data_range.y = max(value,tmp[key].data_range.y)

		for k,p in tmp.items():
		 	p.limit_range = copy.deepcopy(p.data_range)
		# 	print "[%s] range: %f -> %f"%(p.name,p.data_range.x, p.data_range.y)
		
		# Dictionaries are unordered so sort by key name and stick the results in a list
		parallels = [tmp[k] for k in sorted(tmp.keys())]
		
		# iterate over all parallel coordinates and set their position in 2D space
		x = WIDTHPAD/2
		y = HEIGHTPAD/2
		for index,p in enumerate(parallels):
			p.position = Vec2(x,y)
			x += step

		# last step, iterate back over data to create line chains
		for item in data:
			tmp = [item[k] for k in sorted(item.keys())]	
			last_ln = None
			lc = LineChain()
			for index in range(0,len(tmp)):
				v1 = float(tmp[index])
				x1 = parallels[index].position.x + parallels[index].width / 2.0
			 	y1 = parallels[index].domain(v1)
			 	vec1 = Vec2(x1,y1)
			 	lc.add_node(parallels[index],vec1,v1)
			line_chains.append(lc)

def load(file_name):
	ext = os.path.splitext(file_name)[1]

	print "Attempting to load file <%s>"%(file_name)
	if ext in ['.csv','.txt']:
		load_csv(file_name)
	elif ext in ['.json']:
		load_json(file_name)
	else:
		raise ValueError("File type <%d> not supported"%(ext))

def uae():
	print "Usage: python parallel_coordinates <file>"
	print ""
	print "Supported File Types: .csv, .json"
	print "Number of columns should not exceed 6"
	sys.exit(0)

def main():
	argc = len(sys.argv)
	if argc != 2:
		uae()

	load(sys.argv[1])
	build_graph()
	mainloop()
	
if __name__=='__main__':
	main()