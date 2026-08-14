# Remote Toilet

My cat uses the Whisker Litter Robot 3 and loves it.  The data from the application has pointed me to 2 circumstances where she had developed a bladder stone.  Since the data self-deletes after 4 weeks, I am building this app to monitor the daily usage and send alerts if daily usage exceeds a certain threshold, and track usage over a larger period of time.

# Usage
```
docker build -t remote-toilet .

docker run -e WHISKER_USERNAME=your_user -e WHISKER_PASSWORD=your_pass remote-toilet
```