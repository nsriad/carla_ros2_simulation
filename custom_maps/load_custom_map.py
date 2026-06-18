import carla

def main():
    # read xodr file
    with open('straight_highway.xodr', 'r') as f:
        xodr_data = f.read()

    # connect carla server
    client = carla.Client('localhost', 2000)
    client.set_timeout(20.0)

    print("Generating custom flat map... this may take a minute.")
    
    client.generate_opendrive_world(
        xodr_data,
        carla.OpendriveGenerationParameters(
            vertex_distance=2.0,
            max_road_length=50.0,
            wall_height=0.0,   # no walls, no guardrails
            additional_width=0.0,
            smooth_junctions=True,
            enable_mesh_visibility=True
        )
    )
    print("Map loaded successfully! You can now start your ROS 2 bridge.")

if __name__ == '__main__':
    main()
