import carla

CAR_LEN = 4.8  # mkz/tesla pair, same value used for the training ground truth


def check_map(world, map_name):
    # the bridge loads the map, here we only make sure it is the one the config wants
    loaded = world.get_map().name
    if map_name.startswith('xodr:'):
        ok = not loaded.startswith('Carla/Maps/')
    else:
        ok = loaded.endswith(map_name)
    if not ok:
        raise RuntimeError(f'config MAP is {map_name} but carla has {loaded} loaded. '
                           f'start the bridge with the same map (run_platoon.sh does this)')


def spawn_transform(cmap, spec):
    # spec is dict(road_id, lane_id, s) or dict(x, y, z, yaw)
    if 'x' in spec:
        return carla.Transform(carla.Location(x=spec['x'], y=spec['y'], z=spec.get('z', 0.0) + 0.5),
                               carla.Rotation(yaw=spec.get('yaw', 0.0)))
    wp = cmap.get_waypoint_xodr(spec['road_id'], spec['lane_id'], spec['s'])
    if wp is None:
        raise RuntimeError(f'no waypoint at road {spec["road_id"]} lane {spec["lane_id"]} s {spec["s"]}')
    return wp_to_transform(wp)


def wp_to_transform(wp):
    # lift a bit so the car does not spawn inside the road
    t = wp.transform
    return carla.Transform(carla.Location(x=t.location.x, y=t.location.y, z=t.location.z + 0.5), t.rotation)


def spawn_vehicles(world, cfg):
    cmap = world.get_map()
    bp_lib = world.get_blueprint_library()
    vehicles = []
    prev_wp = None
    for v in cfg['VEHICLES']:
        if 'spawn' in v:
            t = spawn_transform(cmap, v['spawn'])
        elif prev_wp is None:
            t = spawn_transform(cmap, cfg['SPAWN'])
        else:
            # gap0 is bumper to bumper, so add one car length between centers
            wp = prev_wp.previous(v.get('gap0', 20.0) + CAR_LEN)[0]
            if v.get('lane', wp.lane_id) != wp.lane_id:
                wp = cmap.get_waypoint_xodr(wp.road_id, v['lane'], wp.s)
            t = wp_to_transform(wp)
        prev_wp = cmap.get_waypoint(t.location)

        bp = bp_lib.find(v.get('blueprint', 'vehicle.tesla.model3'))
        # role_name gives the bridge topics /carla/<name>/...
        bp.set_attribute('role_name', v['name'])
        actor = world.try_spawn_actor(bp, t)
        if actor is None:
            raise RuntimeError(f'could not spawn {v["name"]} at {t.location}, spot is taken')
        vehicles.append(actor)
    return vehicles


def attach_collision(world, vehicle, name, events):
    bp = world.get_blueprint_library().find('sensor.other.collision')
    sensor = world.spawn_actor(bp, carla.Transform(), attach_to=vehicle)
    # the callback runs on a carla thread, so only append here and write the file later
    sensor.listen(lambda e: events.append(dict(
        time=e.timestamp, vehicle=name, other=e.other_actor.type_id,
        other_name=e.other_actor.attributes.get('role_name', ''))))
    return sensor


def cleanup(actors):
    for a in actors:
        if a is not None and a.is_alive:
            if a.type_id.startswith('sensor.'):
                a.stop()
            a.destroy()


# spawn check: python3 world_setup.py <config> [map], used by run_platoon.sh --test
if __name__ == '__main__':
    import sys
    import runpy
    cfg = runpy.run_path(sys.argv[1])
    map_name = sys.argv[2] if len(sys.argv) > 2 else cfg['MAP']
    world = carla.Client('localhost', 2000).get_world()
    check_map(world, map_name)
    print('map ok:', world.get_map().name)
    cars = spawn_vehicles(world, cfg)
    events = []
    sensors = [attach_collision(world, c, c.attributes['role_name'], events) for c in cars]
    # let the bridge tick a few times so the cars settle on the road
    for _ in range(20):
        world.wait_for_tick()
    cmap = world.get_map()
    for c in cars:
        wp = cmap.get_waypoint(c.get_location())
        print(f"{c.attributes['role_name']:8s} {c.type_id:26s} road {wp.road_id} lane {wp.lane_id} s {wp.s:.1f}")
    print('collisions:', events)
    cleanup(sensors + cars)
