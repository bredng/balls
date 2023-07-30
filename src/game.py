import random
import math

import comms
from object_types import ObjectTypes

"""
to-do:
find boundaries and avoid -> DONE
if trapped, shoot walls (check for objects within a certain radius) -> DONE
if enemy nearby, move outward -> DONE
check health, if low health, check for health powerups -> haven't done also each powerup has a diff powerup id
"""


def print2(x):
	import sys
	print(x, file = sys.stderr)


class Game:
	"""
    Stores all information about the game and manages the communication cycle.
    Available attributes after initialization will be:
    - tank_id: your tank id
    - objects: a dict of all objects on the map like {object-id: object-dict}.
    - width: the width of the map as a floating point number.
    - height: the height of the map as a floating point number.
    - current_turn_message: a copy of the message received this turn. It will be updated everytime `read_next_turn_data`
        is called and will be available to be used in `respond_to_turn` if needed.
    """
	
	def __init__(self):
		tank_id_message: dict = comms.read_message()
		self.tank_id = tank_id_message["message"]["your-tank-id"]
		self.enemy_tank_id = tank_id_message["message"]["enemy-tank-id"]
		
		self.last_angle_moved = None
		self.last_enemy_distance = None
		self.my_last_loc = None
		self.low_x = None
		self.big_x = None
		self.low_y = None
		self.big_y = None
		
		self.boundary = None
		self.map_centre = None
		
		self.current_turn_message = None
		
		# We will store all game objects here
		self.objects = {}
		
		next_init_message = comms.read_message()
		while next_init_message != comms.END_INIT_SIGNAL:
			# At this stage, there won't be any "events" in the message. So we only care about the object_info.
			object_info: dict = next_init_message["message"]["updated_objects"]
			
			# Store them in the objects dict
			self.objects.update(object_info)
			
			# Read the next message
			next_init_message = comms.read_message()
		
		# We are outside the loop, which means we must've received the END_INIT signal
		
		# Let's figure out the map size based on the given boundaries
		
		# Read all the objects and find the boundary objects
		boundaries = []
		for game_object in self.objects.values():
			if game_object["type"] == ObjectTypes.BOUNDARY.value:
				boundaries.append(game_object)
		
		# The biggest X and the biggest Y among all Xs and Ys of boundaries must be the top right corner of the map.
		
		# Let's find them. This might seem complicated, but you will learn about its details in the tech workshop.
		biggest_x, biggest_y = [
			max([max(map(lambda single_position: single_position[i], boundary["position"])) for boundary in boundaries])
			for i in range(2)
		]
		
		self.width = biggest_x
		self.height = biggest_y
	
	def read_next_turn_data(self):
		"""
        It's our turn! Read what the game has sent us and update the game info.
        :returns True if the game continues, False if the end game signal is received and the bot should be terminated
        """
		# Read and save the message
		self.current_turn_message = comms.read_message()
		
		if self.current_turn_message == comms.END_SIGNAL:
			return False
		
		# Delete the objects that have been deleted
		# NOTE: You might want to do some additional logic here. For example check if a powerup you were moving towards
		# is already deleted, etc.
		for deleted_object_id in self.current_turn_message["message"]["deleted_objects"]:
			try:
				del self.objects[deleted_object_id]
			except KeyError:
				pass
		
		# Update your records of the new and updated objects in the game
		# NOTE: you might want to do some additional logic here. For example check if a new bullet has been shot or a
		# new powerup is now spawned, etc.
		self.objects.update(self.current_turn_message["message"]["updated_objects"])
		
		return True
	
	def respond_to_turn(self):
		"""
        This is where you should write your bot code to process the data and respond to the game.
        """
		
		# Write your code here... For demonstration, this bot just shoots randomly every turn.
		
		# self.read_next_turn_data()
		
		# Distance from centre of tank to the edge of tank = 9.5 (tank coordinate is the centre of the tank)
		# if distance to other tank is less than tolerance, wiggle and shoot in a circle
		# if not, move to other tanks position
		enemy_tank_loc = self.objects[self.enemy_tank_id]["position"]
		my_tank_loc = self.objects[self.tank_id]["position"]
		
		enemy_tolerance = 200
		shoot_signal = None
		
		enemy_distances = self.calculate_distance(my_tank_loc, enemy_tank_loc)
		enemy_angle = self.calculate_angle(my_tank_loc, enemy_tank_loc)
		
		nearby_objects = self.check_nearby_objects()
		nearby_dest = []  # nearby destructible walls
		
		boundary_positions = self.boundary["position"]
		boundary_x = []
		boundary_y = []
		for i in boundary_positions:
			boundary_x.append(i[0])
			boundary_y.append(i[1])
		
		self.low_x = min(boundary_x)
		self.big_x = max(boundary_x)
		self.low_y = min(boundary_y)
		self.big_y = max(boundary_y)
		
		median_x = (self.big_x + self.low_x) / 2
		median_y = (self.big_y + self.low_y) / 2
		
		self.map_centre = [median_x, median_y]
		
		boundary_safety = self.calculate_boundary_distance()
		
		my_response = {}
		
		# check shooting
		
		for i in nearby_objects:
			if i["type"] == ObjectTypes.DESTRUCTIBLE_WALL.value:
				nearby_dest.append(i)
			
			elif i["type"] == ObjectTypes.WALL.value:
				shoot_signal = False
		
		if len(nearby_dest) > 0:
			angle = self.calculate_angle(my_tank_loc, nearby_dest[0]["position"])
			
			my_response.update({
				"shoot": angle
			})
		
		if enemy_distances[0] < enemy_tolerance:
			if shoot_signal is not False and len(nearby_dest) == 0:
				my_response.update({
					"shoot": enemy_angle
				})
		
		# check movement
		
		if self.my_last_loc is not None:
			if self.my_last_loc == my_tank_loc:
				angle = self.calculate_angle(my_tank_loc, self.map_centre)
				
				my_response.update({
					"move": angle
				})
		
		if boundary_safety is not None:
			#print2("eeee")
			my_response.update({
				"path": self.map_centre
			})
		
		elif enemy_distances[0] > enemy_tolerance:
			destination = self.check_nearby_powerups(nearby_objects)
			my_response.update({
				"path": destination
			})
		
		else:
			tang_angle = self.calculate_tangent_angle()
			
			if self.last_enemy_distance is None:
				my_response.update({
					"move": tang_angle
				})
			
			else:
				if enemy_distances[0] <= self.last_enemy_distance:
					move_angle = int((enemy_angle + tang_angle) / 2)
					
					my_response.update({
						"move": move_angle
					})
		
		self.last_enemy_distance = enemy_distances[0]
		self.my_last_loc = my_tank_loc
		
		comms.post_message(my_response)
	
	def calculate_distance(self, first_location, second_location):
		y_dist = second_location[1] - first_location[1]  # y coordinates
		x_dist = second_location[0] - first_location[0]  # x coordinates
		
		return [math.sqrt(x_dist ** 2 + y_dist ** 2), x_dist, y_dist]
	
	def calculate_angle(self, first_location, second_location) -> int:
		distances = self.calculate_distance(first_location, second_location)
		x_dist = distances[1]
		y_dist = distances[2]
		
		if x_dist == 0:
			if y_dist > 0:
				return 90
			else:
				return 270
		
		if y_dist == 0:
			if x_dist > 0:
				return 0
			else:
				return 180
		
		angle = math.degrees(math.atan2(y_dist, x_dist))
		
		if angle < 0:
			angle += 360
		
		return angle
	
	# def calculate_next_move(self, last_angle_moved) -> int:
	#     if last_angle_moved is None:
	#         return self.calculate_tangent_angle()
	#     else:
	#         angle = int(self.calculate_angle())
	#         return random.randint(angle-90,angle+90) % 360
	
	def calculate_tangent_angle(self):
		my_tank_loc = self.objects[self.tank_id]["position"]
		enemy_tank_loc = self.objects[self.enemy_tank_id]["position"]
		gradient = (enemy_tank_loc[1] - my_tank_loc[1]) / (enemy_tank_loc[0] - my_tank_loc[0])
		tangent = -1 / gradient
		
		angle = math.degrees(math.atan(tangent))
		
		return angle
	
	def calculate_boundary_distance(self):
		my_tank_loc = self.objects[self.tank_id]["position"]
		tolerance = 100
		
		my_tank_x = my_tank_loc[0]
		my_tank_y = my_tank_loc[1]
		
		if my_tank_x - tolerance < self.low_x:
			return 0
		
		if my_tank_x + tolerance > self.big_x:
			return 180
		
		if my_tank_y - tolerance < self.low_y:
			return 90
		
		if my_tank_y + tolerance > self.big_y:
			return 270
		
		return None
	
	def check_nearby_objects(self) -> list:
		my_tank_loc = self.objects[self.tank_id]["position"]
		nearby_objects = []
		
		x_low = my_tank_loc[0] - 40
		x_high = my_tank_loc[0] + 40
		y_low = my_tank_loc[1] - 40
		y_high = my_tank_loc[1] + 40
		
		for object in self.objects.values():
			if object["type"] == ObjectTypes.BOUNDARY.value:
				self.boundary = object
				break
			
			object_x = object["position"][0]
			object_y = object["position"][1]
			if object_x > x_low and object_x < x_high and object_y > y_low and object_y < y_high:
				nearby_objects.append(object)
		
		return nearby_objects
	
	def check_nearby_powerups(self, obj_list):
		for object in obj_list:
			if object["type"] == ObjectTypes.POWERUP.value:
				object_x = object["position"][0]
				object_y = object["position"][1]
				if object_x > self.low_x + 20 and object_x < self.big_x - 20 and object_y > self.low_y + 20 and object_y \
						< self.big_y - 20:
					powerup_dist = self.calculate_distance(self.objects[self.tank_id]["position"], object["position"])
					enemy_dist = self.calculate_distance(self.objects[self.tank_id]["position"], self.objects[
						self.enemy_tank_id]["position"])
					if powerup_dist < enemy_dist * 3:
						return object["position"]
					else:
						return self.objects[self.enemy_tank_id]["position"]
			else:
				break
		return self.objects[self.enemy_tank_id]["position"]

