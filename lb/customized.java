import java.io.*;
import java.net.*;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class LoadBalancer {
	private static final int THREAD_POOL_SIZE = 4;
	private final ServerSocket socket;
	private final DataCenterInstance[] instances;
	int i = 0;	
	int j = 0;

	public LoadBalancer(ServerSocket socket, DataCenterInstance[] instances) {
		this.socket = socket;
		this.instances = instances;
	}

	// Complete this function
	public void start() throws IOException {
		ExecutorService executorService = Executors.newFixedThreadPool(THREAD_POOL_SIZE);
		while (true) {
			// only query cpu utilization once a while
			if (j == 0) {
				// get cpu info from first data center
				URL url0 = new URL(instances[0].getUrl() + ":8080/info/cpu");
        			BufferedReader in0 = new BufferedReader(new InputStreamReader(url0.openStream()));
        			String out0 = in0.readLine();
				float cpu0 = Float.parseFloat(out0.substring(out0.indexOf("<body>") + 6, out0.lastIndexOf("</body>")));
				// get cpu info from second data center
				URL url1 = new URL(instances[1].getUrl() + ":8080/info/cpu");
        			BufferedReader in1 = new BufferedReader(new InputStreamReader(url1.openStream()));
        			String out1 = in1.readLine();
				float cpu1 = Float.parseFloat(out1.substring(out1.indexOf("<body>") + 6, out1.lastIndexOf("</body>")));
				// get cpu info from third data center
				URL url2 = new URL(instances[2].getUrl() + ":8080/info/cpu");
        			BufferedReader in2 = new BufferedReader(new InputStreamReader(url2.openStream()));
        			String out2 = in2.readLine();
				float cpu2 = Float.parseFloat(out0.substring(out2.indexOf("<body>") + 6, out2.lastIndexOf("</body>")));
				// pick the lowest cpu utilized instance
				float cpu = Math.min(cpu0, Math.min(cpu1, cpu2));
				if (cpu == cpu0) i = 0;
				if (cpu == cpu1) i = 1;
				if (cpu == cpu2) i = 2;
			}
			// still do round robin most of the time
			if (i == 0) {
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[0]);
				executorService.execute(requestHandler);
			}
			else if (i == 1) {
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[1]);
				executorService.execute(requestHandler);
			}
			else {
				Runnable requestHandler = new RequestHandler(socket.accept(), instances[2]);
				executorService.execute(requestHandler);
			}
			i = (i + 1) % 3;
			j = (j + 1) % 5;
		}
	}
}
