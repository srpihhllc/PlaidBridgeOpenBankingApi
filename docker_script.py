import docker

client = docker.from_env()

# Run a container with the "alpine" image and echo "hello world"
output = client.containers.run("alpine", ["echo", "hello", "world"])

print(output.decode("utf-8"))
