import java.io.IOException;
import java.net.ServerSocket;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class LoadBalancer {
	private static final int THREAD_POOL_SIZE = 4;
	private final ServerSocket socket;
	private final DataCenterInstance[] instances;
	int i = 0;	

	public LoadBalancer(ServerSocket socket, DataCenterInstance[] instances) {
		this.socket = socket;
		this.instances = instances;
	}

	// Complete this function
	public void start() throws IOException {
		ExecutorService executorService = Executors.newFixedThreadPool(THREAD_POOL_SIZE);
		while (true) {
			// rotate to use each instance
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
		}
	}
}
