#!/usr/bin/env python

import os
import time
import urllib2
import boto.ec2.cloudwatch
from boto.ec2.connection import EC2Connection
from boto.ec2.elb import ELBConnection
from boto.ec2.elb import HealthCheck
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy
from boto.ec2.autoscale.tag import Tag
from boto.ec2.cloudwatch import MetricAlarm

LG_IMAGE = 'ami-76164d1c'
DC_IMAGE = 'ami-f4144f9e'
TYPE = 'm3.medium'
ZONE ='us-east-1d'
REGION ='us-east-1'
SG_NAME = 'all_traffic'
LGSG_NAME = 'lg_all_traffic'
TAGK = 'Project'
TAGV = '0'

print 'Creating security group'
# establish boto connection
conn = EC2Connection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_KEY'])
# create security group
sg = conn.create_security_group(name=SG_NAME, description=SG_NAME)
lgsg = conn.create_security_group(name=LGSG_NAME, description=LGSG_NAME)
# allow all traffic
sg.authorize(ip_protocol='tcp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
sg.authorize(ip_protocol='udp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
lgsg.authorize(ip_protocol='tcp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
lgsg.authorize(ip_protocol='udp', from_port=0, to_port=65535, cidr_ip="0.0.0.0/0")
sgs = [SG_NAME]
print 'Starting load generator'
# initialize load generator instance
reservation = conn.run_instances(LG_IMAGE, instance_type=TYPE, 
				placement=ZONE, security_groups=[LGSG_NAME])
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
print 'Creating ELB'
# initialize elastc load balancer
conn2 = ELBConnection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_KEY'])
# set heartbeat
page = 'HTTP:80' + '/heartbeat?lg=' + lg_instance.dns_name
hc = HealthCheck(interval=20, healthy_threshold=3, unhealthy_threshold=5, target=page)
# set port 80
elb = conn2.create_load_balancer('elb', [ZONE], [(80, 80, 'http')])
# allow all traffic
conn2.apply_security_groups_to_lb('elb', [sg.id])
conn2.configure_health_check('elb', hc)
print elb.dns_name
print 'Creating ASG'
# initialize launch config
conn3 = AutoScaleConnection(os.environ['AWS_ACCESS_KEY_ID'], os.environ['AWS_SECRET_KEY'])
config = LaunchConfiguration(name='config', image_id=DC_IMAGE, security_groups=sgs,
							 instance_type=TYPE, instance_monitoring=True)
conn3.create_launch_configuration(config)
# initialize auto scaling group
ag = AutoScalingGroup(connection=conn3, name='gp', load_balancers=['elb'], availability_zones=[ZONE],
                      health_check_type='ELB', health_check_period=60, launch_config=config,
					  min_size=2, max_size=5, desired_capacity=2,
					  tags=[Tag(key=TAGK, value=TAGV, propagate_at_launch=True,
								resource_id='gp', resource_type='auto-scaling-group')])
conn3.create_auto_scaling_group(ag)
# define the scaling policies
scale_up_policy = ScalingPolicy(name='scale_up', adjustment_type='ChangeInCapacity',
								as_name='gp', scaling_adjustment=1, cooldown=60)
scale_down_policy = ScalingPolicy(name='scale_down', adjustment_type='ChangeInCapacity',
								  as_name='gp', scaling_adjustment=-1, cooldown=60)
# create policies
conn3.create_scaling_policy(scale_up_policy)
conn3.create_scaling_policy(scale_down_policy)
# get ARN for policies
up_policy = conn3.get_all_policies(as_group='gp', policy_names=['scale_up'])[0]
down_policy = conn3.get_all_policies(as_group='gp', policy_names=['scale_down'])[0]
# set up cloudwatch
cloudwatch = boto.ec2.cloudwatch.connect_to_region('us-east-1',
			aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
			aws_secret_access_key=os.environ['AWS_SECRET_KEY'])
scale_up_alarm = MetricAlarm(name='scale_up_on_cpu', namespace='AWS/EC2', metric='CPUUtilization',
							statistic='Average', comparison='>', threshold='80', period='60',
							evaluation_periods=2, alarm_actions=[up_policy.policy_arn],
							dimensions={"AutoScalingGroupName": 'gp'})
scale_down_alarm = MetricAlarm(name='scale_down_on_cpu', namespace='AWS/EC2', metric='CPUUtilization',
							   statistic='Average', comparison='<', threshold='30', period='60',
							   evaluation_periods=2, alarm_actions=[down_policy.policy_arn],
							   dimensions={"AutoScalingGroupName": 'gp'})
# create alarms
cloudwatch.create_alarm(scale_up_alarm)
cloudwatch.create_alarm(scale_down_alarm)


# send submission password to load generator
print 'Sending submission password'
while (1):
	try:
		# make sure load generator is ready
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/password?passwd=' + 
					os.environ['SUB_PASSWORD'],
					timeout = 5)
	except:
		print 'Load generator is not ready yet'
		time.sleep(10)
	else:
		break
print f.read()
print 'Load generator is now ready'
print 'Warming up ELB 1st time'
while (1):
	try:
		# make sure load generator is ready to receive elb
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
						'/warmup?dns=' + elb.dns_name, timeout = 5)
	except:
		print 'Load generator is not ready yet'
		time.sleep(10)
	else:
		break
print f.read()
time.sleep(6*60) # sleep during 6 minutes warmup
print 'ELB is warmed up 1st time'
time.sleep(2*60)
print 'Warming up ELB 2nd time'
while (1):
	try:
		# make sure load generator is ready to receive elb
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/warmup?dns=' + elb.dns_name, timeout = 5)
	except:
		print 'Load generator is not ready yet'
		time.sleep(10)
	else:
		break
print f.read()
time.sleep(6*60) # sleep during 5 minutes warmup
print 'ELB is warmed up 2ndtime'
time.sleep(2*60)
# start test
print 'Starting test'
while (1):
	try:
		f = urllib2.urlopen('http://' + lg_instance.dns_name + 
					'/autoscale?dns=' + elb.dns_name, timeout = 5)
	except:
		print "Load generator is not ready yet"
		time.sleep(10)
	else:
		break
response = f.read()
print response
print 'test started'

# sleep for 48 minutes test
time.sleep(60*60)

# terminate resources
ag.shutdown_instances()
ag.delete()
elb.delete()
sg.delete()
