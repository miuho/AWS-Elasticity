#!/usr/bin/env python

import os
from boto.ec2.connection import EC2Connection
import time
import urllib2

LG_IMAGE = 'ami-76164d1c'
DC_IMAGE = 'ami-f4144f9e'
TYPE = 'm3.medium'
ZONE ='us-east-1d'
SG_NAME = 'all_traffic'
TAGK = 'Project'
TAGV = '0'

print 'Starting load generator'
# establish boto connection
conn = EC2Connection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_KEY'])
# create security group
sg = conn.create_security_group(name=SG_NAME, description=SG_NAME)
# allow all traffic
sg.authorize(ip_protocol='tcp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
sg.authorize(ip_protocol='udp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
sgs = {SG_NAME}
# initialize load generator instance
reservation = conn.run_instances(LG_IMAGE, instance_type=TYPE, 
				placement=ZONE, security_groups=sgs)
lg_instance = reservation.instances[0]
time.sleep(10)
# wait for load generator to run
while not lg_instance.update() == 'running':
	time.sleep(3)
time.sleep(5)
# add tag
lg_instance.add_tag(TAGK, TAGV)
time.sleep(5)
print lg_instance.id
print lg_instance.dns_name
print lg_instance.tags
print 'Starting first data center'
# initialize data center instance
reservation = conn.run_instances(DC_IMAGE, instance_type=TYPE, 
				placement=ZONE, security_groups=sgs)
dc_instance = reservation.instances[0]
time.sleep(10)
# wait for data center to run
while not dc_instance.update() == 'running':
	time.sleep(3)
time.sleep(5)
# add tag
dc_instance.add_tag(TAGK, TAGV)
time.sleep(5)
print dc_instance.id
print dc_instance.dns_name
print dc_instance.tags
# send submission password to load generator
print 'Sending submission password'
while (1):
	try:
		# make sure load generator is ready
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/password?passwd=' + 
					os.environ['SUB_PASSWORD'] +
					'&andrewid=hmiu',
					timeout = 5)
	except:
		print 'Load generator is not ready yet'
		time.sleep(10)
	else:
		break
print f.read()
print 'Load generator is now ready'
print 'Checking first data center'
while (1):
	try:
		# make sure data center is ready
		f = urllib2.urlopen('http://' + dc_instance.dns_name + 
					'/lookup/random', timeout = 5)
	except:
		print 'First data center is not ready yet'
		time.sleep(10)
	else:
		break
print f.read()
print 'First data center is now ready'
# submit data center to load generator
print 'Submitting first data center'
while (1):
	try:
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/test/horizontal?dns=' + 
					dc_instance.dns_name, 
					timeout = 5)
	except:
		print "Load generator is not ready yet"
		time.sleep(10)
	else:
		break
response = f.read()
print response
print 'First data center submitted'
# fetch the test number
test = response[response.find('test.') + len('test.'):response.find('.log')]
print "test is " + test
# check rps and submit more data center if needed
count = 1
while (1):
	print 'Checking rps'
	while (1):
		try:
			f = urllib2.urlopen('http://' + lg_instance.dns_name + 
						'/log?name=test.' + 
						test + '.log', 
						timeout = 5)
		except:
			print "Load generator is not ready yet"
			time.sleep(10)
		else:
			break
	response = f.read()
	print response
	# calculate rps
	rps = 0
	# find the last minute to calculate
	latest = response.rfind('Minute')
	while (latest != -1): 
		begin = response.find('=', latest)
		end = response.find('.', begin)
		if (begin == -1 or end == -1):
			break
		rps += int(response[begin + 1:end])
		latest = end + 1
	print "rps is %i" % rps
	# no need to add more data centers
	if (rps >= 4000):
		break
	# initialize data center instance
	reservation = conn.run_instances(DC_IMAGE, instance_type=TYPE, 
					placement=ZONE, security_groups=sgs)
	dc_instance = reservation.instances[0]
	time.sleep(10)
	# wait for data center to run
	while not dc_instance.update() == 'running':
		time.sleep(3)
	time.sleep(10)
	# add tag
	dc_instance.add_tag(TAGK, TAGV)
	time.sleep(10)
	print dc_instance.id
	print dc_instance.dns_name
	print dc_instance.tags
	print 'Checking new data center'
	while (1):
		try:
			# make sure data center is ready
			f = urllib2.urlopen('http://' + dc_instance.dns_name + 
					'/lookup/random', timeout = 5)
		except:
			print 'Data center is not ready yet'
			time.sleep(10)
		else:
			break
	print f.read()
	print 'Data center is now ready'
	# submit data center to load generator
	print 'Submitting data center'
	while (1):
		try:
			f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/test/horizontal/add?dns=' + 
					dc_instance.dns_name, 
					timeout = 5)
		except:
			print "Load generator is not ready yet"
			time.sleep(10)
		else:
			break
	print f.read()
	count += 1
	print "%i th data center submitted" % count

