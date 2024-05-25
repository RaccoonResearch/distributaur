import os
import sys
import requests
import json
from typing import Dict
import re

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../"))

from distributaur.core import get_env_vars, redis_client, config

server_url_default = "https://console.vast.ai"
headers = {}


def dump_redis_values():
    """
    Prints all keys and their values from the Redis database. It supports multiple data types:
    strings, lists, sets, hashes, and sorted sets. If the data type is unsupported, it prints a warning.
    """
    keys = redis_client.keys("*")
    for key in keys:
        key_type = redis_client.type(key).decode("utf-8")
        if key_type == "string":
            value = redis_client.get(key).decode("utf-8")
            print(f"Key: {key.decode('utf-8')}, Value: {value}")
        elif key_type == "list":
            value = redis_client.lrange(key, 0, -1)
            print(f"Key: {key.decode('utf-8')}, Value: {value}")
        elif key_type == "set":
            value = redis_client.smembers(key)
            print(f"Key: {key.decode('utf-8')}, Value: {value}")
        elif key_type == "hash":
            value = redis_client.hgetall(key)
            print(f"Key: {key.decode('utf-8')}, Value: {value}")
        elif key_type == "zset":
            value = redis_client.zrange(key, 0, -1, withscores=True)
            print(f"Key: {key.decode('utf-8')}, Value: {value}")
        else:
            print(f"Key: {key.decode('utf-8')} has unsupported type: {key_type}")


def http_get(url, headers):
    """
    Sends a GET request to the specified URL with the provided headers.
    Returns the JSON response if successful, and prints and raises any errors encountered during the request.
    
    Args:
        url (str): The URL to send the GET request to.
        headers (dict): The headers to include in the request.
        
    Returns:
        dict: The parsed JSON response from the server.
        
    Raises:
        RequestException: If there is an error during the request.
    """
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if response is not None:
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
        raise


def apiurl(subpath: str, query_args: Dict = None, api_key: str = None) -> str:
    """
    Constructs a full API URL from a subpath, optional query arguments, and an optional API key.
    
    Args:
        subpath (str): The API endpoint subpath.
        query_args (dict, optional): Query parameters to include in the URL.
        api_key (str, optional): API key to include as a query parameter.
        
    Returns:
        str: The fully constructed URL.
    """
    if query_args is None:
        query_args = {}
    if api_key is not None:
        query_args["api_key"] = api_key
    query_json = "&".join(
        "{x}={y}".format(x=x, y=requests.utils.quote(json.dumps(y)))
        for x, y in query_args.items()
    )
    return server_url_default + "/api/v0" + subpath + "?" + query_json


def http_put(req_url, headers, json):
    """
    Sends a PUT request to the specified URL with the provided headers and JSON payload.
    Returns the response if the request is successful.
    
    Args:
        req_url (str): The URL to send the PUT request to.
        headers (dict): The headers to include in the request.
        json (dict): The JSON payload for the request.
        
    Returns:
        Response: The response object from the request.
    """
    response = requests.put(req_url, headers=headers, json=json)
    response.raise_for_status()
    return response


def http_del(req_url, headers, json={}):
    """
    Sends a DELETE request to the specified URL with the provided headers and optional JSON payload.
    Returns the response if the request is successful.
    
    Args:
        req_url (str): The URL to send the DELETE request to.
        headers (dict): The headers to include in the request.
        json (dict, optional): The JSON payload for the request.
        
    Returns:
        Response: The response object from the request.
    """
    response = requests.delete(req_url, headers=headers, json=json)
    response.raise_for_status()
    return response


def http_post(req_url, headers, json={}):
    """
    Sends a POST request to the specified URL with the provided headers and optional JSON payload.
    Attempts to handle any exceptions that occur and prints detailed error responses.
    
    Args:
        req_url (str): The URL to send the POST request to.
        headers (dict): The headers to include in the request.
        json (dict, optional): The JSON payload for the request.
        
    Returns:
        Response: The response object from the request.
        
    Raises:
        RequestException: If there is an error with the request.
    """
    response = requests.post(req_url, headers=headers, json=json)
    try:
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error response content: {response.content}")
        raise e
    return response


def parse_query(
    query_str: str, res: Dict = None, fields={}, field_alias={}, field_multiplier={}
) -> Dict:
    """
    Parses a string query into a structured dictionary using specified fields, aliases, and multipliers.
    Supports various comparison operators and complex queries.
    
    Args:
        query_str (str): The query string to parse.
        res (dict, optional): The dictionary to populate with the parsed query.
        fields (dict, optional): Recognized fields for validation.
        field_alias (dict, optional): Aliases for fields to allow flexible query syntax.
        field_multiplier (dict, optional): Multipliers for certain fields for unit conversion.
        
    Returns:
        dict: A dictionary representation of the query.
        
    Raises:
        ValueError: If there are syntax errors in the query.
    """
    if res is None:
        res = {}
    if type(query_str) == list:
        query_str = " ".join(query_str)
    query_str = query_str.strip()
    pattern = r"([a-zA-Z0-9_]+)( *[=><!]+| +(?:[lg]te?|nin|neq|eq|not ?eq|not ?in|in) )?( *)(\[[^\]]+\]|\"[^\"]+\"|[^ ]+)?( *)"
    opts = re.findall(pattern, query_str)
    op_names = {
        ">=": "gte",
        ">": "gt",
        "gt": "gt",
        "gte": "gte",
        "<=": "lte",
        "<": "lt",
        "lt": "lt",
        "lte": "lte",
        "!=": "neq",
        "==": "eq",
        "=": "eq",
        "eq": "eq",
        "neq": "neq",
        "noteq": "neq",
        "not eq": "neq",
        "notin": "notin",
        "not in": "notin",
        "nin": "notin",
        "in": "in",
    }
    joined = "".join("".join(x) for x in opts)
    if joined != query_str:
        raise ValueError(
            "Unconsumed text. Did you forget to quote your query? "
            + repr(joined)
            + " != "
            + repr(query_str)
        )
    for field, op, _, value, _ in opts:
        value = value.strip(",[]")
        v = res.setdefault(field, {})
        op = op.strip()
        op_name = op_names.get(op)
        if field in field_alias:
            res.pop(field)
            field = field_alias[field]
        if not field in fields:
            print(
                "Warning: Unrecognized field: {}, see list of recognized fields.".format(
                    field
                ),
                file=sys.stderr,
            )
        if not op_name:
            raise ValueError(
                "Unknown operator. Did you forget to quote your query? "
                + repr(op).strip("u")
            )
        if op_name in ["in", "notin"]:
            value = [x.strip() for x in value.split(",") if x.strip()]
        if not value:
            raise ValueError(
                "Value cannot be blank. Did you forget to quote your query? "
                + repr((field, op, value))
            )
        if not field:
            raise ValueError(
                "Field cannot be blank. Did you forget to quote your query? "
                + repr((field, op, value))
            )
        if value in ["?", "*", "any"]:
            if op_name != "eq":
                raise ValueError("Wildcard only makes sense with equals.")
            if field in v:
                del v[field]
            if field in res:
                del res[field]
            continue
        if isinstance(value, str):
            value = value.replace("_", " ")
            value = value.strip('"')
        elif isinstance(value, list):
            value = [x.replace("_", " ") for x in value]
            value = [x.strip('"') for x in value]
        if field in field_multiplier:
            value = float(value) * field_multiplier[field]
            v[op_name] = value
        else:
            if (value == "true") or (value == "True"):
                v[op_name] = True
            elif (value == "false") or (value == "False"):
                v[op_name] = False
            elif (value == "None") or (value == "null"):
                v[op_name] = None
            else:
                v[op_name] = value
        if field not in res:
            res[field] = v
        else:
            res[field].update(v)
    return res


offers_fields = {
    "bw_nvlink",
    "compute_cap",
    "cpu_cores",
    "cpu_ram",
    "cuda_max_good",
    "direct_port_count",
    "disk_bw",
    "disk_space",
    "dlperf",
    "dph_total",
    "driver_version",
    "duration",
    "external",
    "flops_per_dphtotal",
    "gpu_mem_bw",
    "gpu_name",
    "gpu_ram",
    "has_avx",
    "id",
    "inet_down",
    "inet_down_cost",
    "inet_up",
    "inet_up_cost",
    "machine_id",
    "min_bid",
    "mobo_name",
    "num_gpus",
    "pci_gen",
    "pcie_bw",
    "reliability",
    "rentable",
    "rented",
    "storage_cost",
    "total_flops",
    "verified",
}

offers_alias = {
    "cuda_vers": "cuda_max_good",
    "reliability": "reliability2",
    "dlperf_usd": "dlperf_per_dphtotal",
    "dph": "dph_total",
    "flops_usd": "flops_per_dphtotal",
}

offers_mult = {"cpu_ram": 1000, "duration": 24 * 60 * 60}


def get_runtype(args):
    runtype = "ssh"
    if args.jupyter_dir or args.jupyter_lab:
        args.jupyter = True
    if args.jupyter and runtype == "args":
        print(
            "Error: Can't use --jupyter and --args together. Try --onstart or --onstart-cmd instead of --args.",
            file=sys.stderr,
        )
        return 1
    if args.jupyter:
        runtype = (
            "jupyter_direc ssh_direc ssh_proxy"
            if args.direct
            else "jupyter_proxy ssh_proxy"
        )
    if args.ssh:
        runtype = "ssh_direc ssh_proxy" if args.direct else "ssh_proxy"
    return runtype


def parse_env(envs):
    result = {}
    if envs is None:
        return result
    env = envs.split(" ")
    prev = None
    for e in env:
        if prev is None:
            if e in {"-e", "-p", "-h"}:
                prev = e
            else:
                return result
        else:
            if prev == "-p":
                if set(e).issubset(set("0123456789:tcp/udp")):
                    result["-p " + e] = "1"
                else:
                    return result
            elif prev == "-e":
                kv = e.split("=")
                if len(kv) >= 2:
                    val = kv[1].strip("'\"")
                    result[kv[0]] = val
                else:
                    return result
            else:
                result[prev] = e
            prev = None
    return result


import urllib.parse


def search_offers(max_price):
    """
    Searches for offers below a specified maximum price using an API.
    Constructs the search URL and handles the request, returning a list of offers if successful.
    
    Args:
        max_price (float): The maximum price to filter the offers.
        
    Returns:
        list: A list of offers that match the criteria.
        
    Raises:
        RequestException: If there is an error during the request.
    """
    api_key = config.get("VAST_API_KEY")
    base_url = "https://console.vast.ai/api/v0/bundles/"
    print("api_key")
    print(api_key)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    url = (
        base_url
        + '?q={"gpu_ram":">=4","rentable":{"eq":true},"dph_total":{"lte":'
        + str(max_price)
        + '},"sort_option":{"0":["dph_total","asc"],"1":["total_flops","asc"]}}'
    )

    print("url", url)

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        json = response.json()
        return json["offers"]

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        print(f"Response: {response.text if response else 'No response'}")
        raise


def create_instance(offer_id, image, env):
    """
    Creates a virtual machine instance using the specified offer ID, image, and environment settings.
    Prepares the environment and handles the API call for instance creation.
    
    Args:
        offer_id (str): The ID of the offer to use for creating the instance.
        image (str): The image to use for the instance.
        env (dict): The environment settings necessary for the instance.
        
    Returns:
        dict: A dictionary containing details of the created instance.
        
    Raises:
        ValueError: If the environment is not properly configured or missing required keys.
    """
    if env is None:
        raise ValueError("env is required")

    if not isinstance(env, dict):
        raise ValueError("env must be a dictionary")

    if not "VAST_API_KEY" in env:
        # warn about missing vast api key
        print("Warning: Missing Vast API key")

    json_blob = {
        "client_id": "me",
        "image": image,
        "env": "",
        "disk": 16,  # Set a non-zero value for disk
        "onstart": f"export PATH=$PATH:/ &&  cd ../ && REDIS_HOST={config.get('REDIS_HOST')} REDIS_PORT={config.get('REDIS_PORT')} REDIS_USER={config.get('REDIS_USER')} REDIS_PASSWORD={config.get('REDIS_PASSWORD')} HF_TOKEN={config.get('HF_TOKEN')} HF_REPO_ID={config.get('HF_REPO_ID')} HF_PATH={config.get('HF_PATH')} VAST_API_KEY={config.get('VAST_API_KEY')} celery -A simian.worker worker --loglevel=info",
        "runtype": "ssh ssh_proxy",
        "image_login": None,
        "python_utf8": False,
        "lang_utf8": False,
        "use_jupyter_lab": False,
        "jupyter_dir": None,
        "create_from": "",
        "template_hash_id": "250671155ccbc28d0609af524b75a80e",
        "template_id": 108305,
    }
    url = apiurl(f"/asks/{offer_id}/")
    response = http_put(
        url,
        headers={
            "Authorization": f"Bearer {env['VAST_API_KEY']}",
        },
        json=json_blob,
    )

    # check on response
    if response.status_code != 200:
        print(f"Failed to create instance: {response.text}")
        raise Exception(f"Failed to create instance: {response.text}")

    return response.json()


def destroy_instance(instance_id):
    """
    Destroys a virtual machine instance specified by its ID.
    Handles the API call to terminate the instance.
    
    Args:
        instance_id (str): The ID of the instance to terminate.
        
    Returns:
        dict: A dictionary containing the server response after attempting to terminate the instance.
    """
    api_key = config.get("VAST_API_KEY")
    headers = {"Authorization": f"Bearer {api_key}"}
    url = apiurl(f"/instances/{instance_id}/")
    # print(f"Terminating instance: {instance_id}")
    response = http_del(url, headers=headers, json={})
    return response.json()


def rent_nodes(max_price, max_nodes, image, api_key, env=get_env_vars(".env")):
    """
    Searches for and rents nodes based on specified criteria such as maximum price and node count.
    Handles node creation for each valid offer and returns a list of rented nodes with their details.
    
    Args:
        max_price (float): The maximum price per hour for the nodes.
        max_nodes (int): The maximum number of nodes to rent.
        image (str): The image identifier to be used for the nodes.
        api_key (str): The API key required for authentication with the service.
        env (dict, optional): The environment variables used for additional configuration.
        
    Returns:
        list: A list of dictionaries, each containing the details of a rented node including offer ID and instance ID.
        
    Raises:
        HTTPError: If there is an error during the renting process due to an HTTP issue.
    """
    api_key = api_key or env.get("VAST_API_KEY")
    offers = search_offers(max_price)
    rented_nodes = []
    for offer in offers:
        if len(rented_nodes) >= max_nodes:
            break
        try:
            instance = create_instance(offer["id"], image, env)
            rented_nodes.append(
                {"offer_id": offer["id"], "instance_id": instance["new_contract"]}
            )
            # print(f"Rented node {offer['id']} on contract: {instance['new_contract']}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400 or e.response.status_code == 404:
                # print the response itself
                # print(f"Error renting node: {offer['id']}, {e.response.text}")
                # print(f"Offer {offer['id']} is unavailable. Trying next offer...")
                pass
            else:
                # print(f"Error renting node: {offer['id']}, {str(e)}")
                raise
    return rented_nodes


def terminate_nodes(nodes):
    """
    Terminates a list of nodes by sending a termination request for each node's instance ID.
    This function ensures that all specified nodes are properly shut down.
    
    Args:
        nodes (list of dicts): A list of node dictionaries, each containing at least an 'instance_id' key.
        
    Raises:
        Exception: If an error occurs during the termination of any node.
    """
    for node in nodes:
        try:
            destroy_instance(node["instance_id"])
        except Exception as e:
            print(f"Error terminating node: {node['instance_id']}, {str(e)}")


def handle_signal(nodes):
    """
    Creates and returns a signal handler for gracefully shutting down nodes upon receiving a SIGINT (Ctrl-C).
    This function is particularly useful for ensuring a clean and controlled shutdown of resources.
    
    Args:
        nodes (list): A list of node dictionaries that need to be terminated upon signal reception.
        
    Returns:
        function: A signal handler function that can be set as the handler for SIGINT.
    """
    from distributaur.vast import terminate_nodes

    def signal_handler(sig, frame):
        print("SIGINT received, shutting down...")
        terminate_nodes(nodes)
        sys.exit(0)

    return signal_handler
