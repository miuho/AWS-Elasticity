import java.io.*;
import java.net.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.ArrayList;
import java.util.List;
import java.util.Properties;
import com.amazonaws.auth.BasicAWSCredentials;
import com.amazonaws.services.ec2.AmazonEC2Client;
import com.amazonaws.services.ec2.model.Placement;
import com.amazonaws.services.ec2.model.DescribeInstanceStatusRequest;
import com.amazonaws.services.ec2.model.DescribeInstanceStatusResult;
import com.amazonaws.services.ec2.model.DescribeInstancesRequest;
import com.amazonaws.services.ec2.model.DescribeInstancesResult;
import com.amazonaws.services.ec2.model.Tag;
import com.amazonaws.services.ec2.model.Instance;
import com.amazonaws.services.ec2.model.InstanceStatus;
import com.amazonaws.services.ec2.model.RunInstancesRequest;
import com.amazonaws.services.ec2.model.RunInstancesResult;

public class LoadBalancer {
	private static final int THREAD_POOL_SIZE = 4;
	private final ServerSocket socket;
	private final DataCenterInstance[] instances;
	int i = 0;
	int j = 0;
	int[] running;
	AmazonEC2Client ec2;
	String id0;
	String id1;
	String id2;
	
	public LoadBalancer(ServerSocket socket, DataCenterInstance[] instances) {
		this.socket = socket;
		this.instances = instances;
		try {
			// load credentials
			Properties properties = new Properties();
			properties.load(LoadBalancer.class.getResourceAsStream("/AwsCredentials.properties"));
			BasicAWSCredentials cred = new BasicAWSCredentials(
				properties.getProperty("accessKey"),
				properties.getProperty("secretKey"));
			// initially all 3 instances are running
			this.running = new int[3];
			this.running[0] = 1;
			this.running[1] = 1;
			this.running[2] = 1;
			// create ec2 client
			this.ec2 = new AmazonEC2Client(cred);
		} catch(Exception e) {}
	}
	
	public float check_cpu(int n) {
		// get cpu info by pinging
		float cpu = 0;
		try {
			URL url = new URL(instances[n].getUrl() + ":8080/info/cpu");
        		BufferedReader in = new BufferedReader(new InputStreamReader(url.openStream()));
        		String out = in.readLine();
			// get the cpu from the message body
			cpu = Float.parseFloat(out.substring(out.indexOf("<body>") + 6, out.lastIndexOf("</body>")));
		} catch(Exception e) {}
		return cpu;
	}

	public int is_running(int n) {
		// check the cached running state to speed up checking
		if (running[n] == 1) return 1;
		try {
			// get the instance ID
			String id;
			if (n == 0) id = id0;	
			if (n == 1) id = id1;	
			else id = id2;	
			// check the instance
			DescribeInstancesRequest d = new DescribeInstancesRequest().withInstanceIds(id);
			DescribeInstancesResult r = ec2.describeInstances(d);
			Instance instance = r.getReservations().get(0).getInstances().get(0);
			// try to ping the host
			URL url = new URL("http://" + instance.getPublicDnsName());
			URLConnection con = url.openConnection();
     			// set the connection timeout
     			con.setConnectTimeout(2000);
    			con.setReadTimeout(2000);
			// open stream
    	 		BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
			// add new instance
			instances[n] = new DataCenterInstance("instance " + Integer.toString(n), "http://" + instance.getPublicDnsName());
			running[n] = 1;
			System.out.println("now running");
		} catch(Exception e1) {
			// url testing failed, new instance is not ready yet
			return 0;
		}
		return 1;
	}
	
	public void launchNew(int n) throws Exception {
		RunInstancesRequest runInstancesRequest = new RunInstancesRequest();
		// make sure all instances are in the same availability zone
		Placement placement = new Placement("us-east-1d");
		// configure instance
		runInstancesRequest.withImageId("ami-ed80c388")
		.withInstanceType("m3.medium")
		.withMinCount(1)
		.withMaxCount(1)
		.withSecurityGroups("all_traffic")
		.withPlacement(placement)		
		.withKeyName("Project2");
		// launch instance
		RunInstancesResult runInstancesResult = ec2.runInstances(runInstancesRequest);
		Instance instance = runInstancesResult.getReservation().getInstances().get(0);
		// remember the new instance's ID
		if (n == 0) id0 = instance.getInstanceId();	
		if (n == 1) id1 = instance.getInstanceId();	
		if (n == 2) id2 = instance.getInstanceId();	
	}

	public void ping(int n) {
		// try to ping the nth data center
		try {
			URL url = new URL(instances[n].getUrl());
			URLConnection con = url.openConnection();
     			// set the connection timeout
     			con.setConnectTimeout(3000);
    			con.setReadTimeout(3000);
			// open stream
     			BufferedReader in = new BufferedReader(new InputStreamReader(con.getInputStream()));
		} catch(Exception e1) {
			System.out.println("url failed");
			running[n] = 0;
			instances[n] = null;
			// data center failed so launch new
			try {
				launchNew(n);
			} catch(Exception e2) {
				System.out.println("launch failed");
			}
		}
	}

	// Complete this function
	public void start() throws IOException {
		ExecutorService executorService = Executors.newFixedThreadPool(THREAD_POOL_SIZE);
		i = 0;
		j = 0;
		while (true) {
			// check cpu once a while
			if (j == 0) {
				float cpu0 = check_cpu(0);
				float cpu1 = check_cpu(1);
				float cpu2 = check_cpu(2);
				// pick the lowest cpu utilized data center
				float cpu = Math.min(cpu0, Math.min(cpu1, cpu2));
				if (cpu == cpu0) i = 0;
				if (cpu == cpu1) i = 1;
				if (cpu == cpu2) i = 2;
			}
			// round robin each data center
			if (i == 0) {
				// check if the instance is running
				if (is_running(0) == 0) {
					// skip to next instance if not running
					i = (i + 1) % 3;
					continue;
				}
				// ping the instance and see if it is ready to receive packet
				ping(0);
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[0]);
				executorService.execute(requestHandler);
			}
			else if (i == 1) {
				if (is_running(1) == 0) {
					i = (i + 1) % 3;
					continue;
				}
				ping(1);
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[1]);
				executorService.execute(requestHandler);
			}
			else {
				if (is_running(2) == 0) {
					i = (i + 1) % 3;
					continue;
				}
				ping(2);
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[2]);
				executorService.execute(requestHandler);
			}
			// pick next instance 
			i = (i + 1) % 3;
			j = (j + 1) % 5;
		}
	}
}
