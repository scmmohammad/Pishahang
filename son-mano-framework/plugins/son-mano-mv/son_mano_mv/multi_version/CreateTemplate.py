import yaml
import random
import logging
import csv
from son_mano_mv.multi_version import TemplateSchema as Template
from son_mano_mv.multi_version import main_auto as main_auto

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:mv")
LOG.setLevel(logging.INFO)


def create_template(payload):
    """
    Extracts descriptor, functions, virtual links from the payload and applies different utility functions on the payload.
    :param payload: receives payload information from the multi version plugin
    :return: generated result file path
    """
    content = payload
    descriptor = content['nsd'] if 'nsd' in content else content['cosd']
    functions = content['functions']
    virtual_links = descriptor['virtual_links']
    pull_component_set(descriptor, functions)
    process_inputs_outputs(virtual_links)
    process_resource_demands()
    process_virtual_links(virtual_links)
    template = create_source_component_dict(descriptor)
    '''
    Calls main_auto method and returns path of the result file generated.
    @argument1: 'heuristic' runs heuristic algorithm on the template created to produce the results
    @argument2: Path to the scenario file containing path of template, source and other required files.
    '''
    result_file = main_auto.main_auto('heuristic', '/plugins/son-mano-mv/son_mano_mv/multi_version/parameters/scenarios/eval-scen1-mulv.csv')
    return result_file


# def read_file():
#    with open("payload.yaml", 'r') as stream:
#        try:
#            payload = stream.read()
#           content = yaml.load(payload)
#        except yaml.YAMLError as exc:
#            print(exc)
#    return content


def pull_component_set(descriptor, functions):
    """
    Creates list of Components from the descriptor.
    :param descriptor: contains the descriptor of the network service.
    :param functions: contains list of virtual functions
    :return:
    """
    # print(functions[0]['vnfd']['virtual_deployment_units'][0]['resource_requirements']['cpu'])
    for network_function in descriptor['network_functions']:
        component_name = network_function['vnf_name']
        component_id = network_function['vnf_id']
        component = Template.Components(component_name, component_id, 'normal', False, 0, 0, [], [-1, -1], 0)
        Template.components.append(component)
    for function in functions:
        for component in Template.components:
            if component_name == function['vnfd']['name']:
                component.cpu_req = function['vnfd']['virtual_deployment_units'][0]['resource_requirements']['cpu']['vcpus']
        # print(function['vnfd']['virtual_deployment_units'][0]['resource_requirements']['cpu'])


def process_inputs_outputs(virtual_links):
    links = []
    for virtual_link in virtual_links:
        if virtual_link['connectivity_type'] == 'E-Line':
            links.append(virtual_link['connection_points_reference'])
    for component in Template.components:
        for link in links:
            if (component.id in link[0] and 'input' in link[0]) or (component.id in link[1] and 'input' in link[1]):
                component.inputs = component.inputs + 1
            if (component.id in link[0] and 'output' in link[0]) or \
                    (component.id in link[1] and 'output' in link[1]):
                if link[0] == 'output' or link[1] == 'output':
                    continue
                else:
                    component.outputs = component.outputs + 1


def process_resource_demands():
    """
    sets the resource demand in the components of the template.
    """
    for component in Template.components:
        component.resource_demands = process_demand(component)
        # demand = process_demand(resource_demand_vm)


def process_demand(component):
    """
    Creates demands for the component (resource demand, demand_vm, demand_accelerated, time, etc.) Considers dummy data
    rate intervals.
    :param component: Component for which resource demand needs to be generated.
    :return: resource demands with all its properties set.
    """
    resource_demand = []
    demand_vm = []
    demand_accelerated = []
    random_number = random.randint(1, 5)
    outputs = []
    boundary = [[0, 9.99999], [10, 24.99999], [25, 74.99999], [75, 1000]]

    # out
    if component.outputs == 1:
        output = [1, 0]
        outputs.append(output)
    elif component.outputs > 1:
        k = 1
        total = 0
        for i in range(component.outputs - 1):
            n = round(random.uniform(0, k), 1)
            output = [n, 0]
            total = total + n
            outputs.append(output)
            k = n - 1
        output = [(1 - total), 0]
        outputs.append(output)
    # VM
    time = random_number  # Change it to 5 to get as_accelerated component in the result file
    cpu = get_cpu_req_vm(component.cpu_req)
    demand = Template.Demand(boundary, cpu, [], outputs, time)
    demand_vm.append(demand)
    resource_demand_vm = Template.ResourceDemands("vm", demand_vm)
    resource_demand.append(resource_demand_vm)

    # Accelerated
    time = random_number / 2.5  # Change it to 0.25 to get as_accelerated component in the result file
    cpu = get_cpu_req_acc()
    gpu = get_gpu_req_acc()
    demand = Template.Demand(boundary, cpu, gpu, outputs, time)
    demand_accelerated.append(demand)
    resource_demand_accelerated = Template.ResourceDemands("accelerated", demand_accelerated)
    resource_demand.append(resource_demand_accelerated)

    return resource_demand


def process_virtual_links(virtual_links):
    """
    Creates objects of Virtual Links from the descriptor for the template.
    :param virtual_links: list of Virtual Links
    :return: Does not return anything.
    """
    links = []
    for virtual_link in virtual_links:
        if virtual_link['connectivity_type'] == 'E-Line':
            links.append(virtual_link['connection_points_reference'])
    max_delay = random.randint(1, 100)  # Considers some randomly generated dummy number for max delay.
    for virtual_link in links:
        if virtual_link[0] == 'input' or virtual_link[1] == 'input':
            if virtual_link[0] == 'input':
                vnf = virtual_link[1].split(":")
                v_link = Template.VLink("S", 0, vnf[0], 0, max_delay)
                Template.virtual_links.append(v_link)
            if virtual_link[1] == 'input':
                vnf = virtual_link[0].split(":")
                v_link = Template.VLink("S", 0, vnf[0], 0, max_delay)
                Template.virtual_links.append(v_link)
        elif virtual_link[0] == 'output' or virtual_link[1] == 'output':
            continue
        else:
            vnf_1 = virtual_link[0].split(":")
            vnf_2 = virtual_link[1].split(":")
            v_link = Template.VLink(vnf_1[0], 0, vnf_2[0], 0, max_delay)
            Template.virtual_links.append(v_link)


def get_cpu_req_vm(cpu_req):
    """
    Generates random array of CPU requirements for data rate intervals.
    :param cpu_req: number of cpu required by the virtual function
    :return: List of number of CPUs required (First element represents minimum CPU requirement, second element represents
    maximum CPU requirement. Example: [1,3] for data rate [10, 24.99999]
    """
    cpu = []
    for i in range(3):
        cpu.append([0, cpu_req])
    cpu.append([0, 5001])
    return cpu


def get_cpu_req_acc():
    """
    Generates random array of CPU requirements for data rate intervals for Accelerated version of resource.
    :return: List of number of CPUs required (First element represents minimum CPU requirement, second element represents
    maximum CPU requirement. Example: [1,3] for data rate [10, 24.99999]
    """
    cpu = []
    k = 1
    for i in range(3):
        x = round(random.uniform(0, 0.1), 2)
        y = random.randint(k, 3)
        cpu.append([x, y])
        k = y
    cpu.append([0, 5001])
    return cpu


def get_gpu_req_acc():
    """
    Generates random GPU requirements for data rate intervals.
    :return: List of number of GPUs required (First element represents minimum GPU requirement, second element represents
    maximum GPU requirement. Example: [1,3] for data rate [10, 24.99999]
    """
    gpu = []
    k = 1
    for i in range(3):
        x = 0
        y = random.randint(1, 3)
        gpu.append([0, y])
        k = y
    gpu.append([0, 5001])
    return gpu


def update_scenario_file(template_filename):
    """
    Updates the scenario file with the name of newly created template file name.
    :param template_filename: name of the template file created.
    :return: Does not return anything, just updates the file.
    """
    template_filename = 'templates: ../templates/' + template_filename
    scenario_file = "/plugins/son-mano-mv/son_mano_mv/multi_version/parameters/scenarios/eval-scen1-mulv.csv"

    # read the scenario file.
    with open(scenario_file, 'r') as csvFile:
        reader = csv.reader(csvFile)
        lines = list(reader)
        found_at = 0
        for index, line in enumerate(lines):
            if len(line) == 1 and "templates:" in line[0]:
                line[0] = template_filename
                found_at = index
        lines[found_at][0] = template_filename

    # update the scenario file.
    with open(scenario_file, 'w') as writeFile:
        writer = csv.writer(writeFile)
        writer.writerows(lines)


def create_source_component_dict(descriptor):
    """
    Creates the source component, creates different dicts to hold different components and its properties and in the end
    writes them to a yaml template file.
    :param descriptor: Takes descriptor to pull the name.
    :return: Does not return anything. Creates a template file in the end.
    """
    # print(descriptor['name'])
    file_name = descriptor['name']
    components = []

    source_demand_dict = dict(
        boundary=[[0, 9.99999], [10, 24.99999], [25, 74.99999], [75, 1000]],  # Dummy data rate intervals
        cpu=[[0, 0], [0, 0], [0, 0], [0, 0]],  # Number of CPUs required for source component is always 0
        out=[1, 0],
        time=0  # Since there is no processing happening on source, time is 0
    )
    resource_demands = []
    source_resource_demands_dict = dict(
        resource_type="vm",
        demand=source_demand_dict
    )
    resource_demands.append(source_resource_demands_dict)
    source_component_dict = dict(
        name='S',
        type="source",
        stateful=False,
        inputs=0,
        outputs=1,
        resource_demands=resource_demands,
        group=[-1, -1]
    )
    components.append(source_component_dict)

    for component in Template.components:
        resource_demands_other = []
        for resource_demand in component.resource_demands:
            for demand_temp in resource_demand.demand:
                if len(demand_temp.gpu) == 0:
                    demand_dict = dict(
                        boundary=demand_temp.boundary,
                        cpu=demand_temp.cpu,
                        out=demand_temp.out,
                        time=demand_temp.time
                    )
                else:
                    demand_dict = dict(
                        boundary=demand_temp.boundary,
                        cpu=demand_temp.cpu,
                        gpu=demand_temp.gpu,
                        out=demand_temp.out,
                        time=demand_temp.time
                    )
            resource_demands_component = dict(
                resource_type=resource_demand.resource_type,
                demand=demand_dict
            )
            resource_demands_other.append(resource_demands_component)
        component_dict = dict(
            name=component.id,
            type=component.type,
            stateful=False,
            inputs=component.inputs,
            outputs=component.outputs,
            resource_demands=resource_demands_other,
            group=[-1, -1]
        )
        components.append(component_dict)

    vlinks = []
    for virtual_link in Template.virtual_links:
        virtual_link = dict(
            src=virtual_link.src,
            src_output=virtual_link.src_output,
            dest=virtual_link.dest,
            dest_input=virtual_link.dest_input,
            max_delay=virtual_link.max_delay
        )
        vlinks.append(virtual_link)

    template_dict = dict(
        name=file_name,
        components=components,
        vlinks=vlinks
    )

    # print("creating template file: " + file_name)
    no_alias_dumper = yaml.SafeDumper
    no_alias_dumper.ignore_aliases = lambda self, data: True
    with open("/plugins/son-mano-mv/son_mano_mv/multi_version/parameters/templates/" + file_name + '.yaml', 'w') as template_file:
        yaml.dump(template_dict, template_file, default_flow_style=False, Dumper=no_alias_dumper)
    update_scenario_file(file_name + '.yaml')  # After creating the template, this method updates the scenario file with
    # newly created template file name.

    return template_dict


def get_name_id_mapping(descriptor):
    """
    Creates a list of key, value pairs of the name and function id of virtual network function
    :param descriptor: descriptor of the network service
    :return: List of name, id pairs of the functions consists in the service descriptor.
    """
    name_id_mapping = []
    virtual_functions = descriptor['network_functions']
    for virtual_function in virtual_functions:
        name_id = [virtual_function['vnf_name'], virtual_function['vnf_id']]
        name_id_mapping.append(name_id)
    return name_id_mapping


def get_function_id(function_name, name_id_mapping):
    """
    Returns the function_id of the Virtual function.
    :param function_name: name of the virtual function.
    :param name_id_mapping: List of key, value pair of the name as key and function id as value.
    :return: virtual function name.
    """
    for name_id in name_id_mapping:
        if function_name == name_id[0]:
            return name_id[1]


