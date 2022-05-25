# Splice

Splice is an automated framework for combining IaaS and FaaS services in a cost- and performance-conscious manner.

# Description

Loadcat - Configuration tool for NGINX (loadbalancer)

Trace - Request Generator for mimicking real-world web services

# How to use

1. Install loadcat and launch few initial server instances (reference loadcat repo)

2. Put your configuration in utils/conf.ini

```
[AWS]
security_group = <>
key_name = <>

[Server]
ami_id = <>
instance_type = c5.2xlarge
number_of_instances = 2
snid = <>
region_name = us-east-1
az = us-east-1f
tag_name = <>

[Performance-Cost]
max_requests_per_sec_per_vm = 23
slo_criteria = 1000

[Workload-Input]
trace_type = wits
input_csv = <>
use_case_for_experiment = <>
cpu_idle_percent = 10
slo_criteria = 1000
over_provision = False
request_type = vm
```

3. Run Controller (controller.py)


See description in compiler.py 






