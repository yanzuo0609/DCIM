# Example Scenarios - 示例场景

## 1. 场景1：三层架构完整部署

```yaml
name: "Three-Tier Network Deployment"
description: "完整的3层网络架构部署"

devices:
  Core层:
    - id: core-1
      name: Core-SW-01
      role: CORE_SWITCH
      rack: RACK-01
      rack_unit: 40
      ports: 48
    
    - id: core-2
      name: Core-SW-02
      role: CORE_SWITCH
      rack: RACK-02
      rack_unit: 40
      ports: 48

  Aggregation层:
    - id: agg-1
      name: Agg-SW-01
      role: AGGREGATION_SWITCH
      rack: RACK-03
      rack_unit: 20
      ports: 48
    
    - id: agg-2
      name: Agg-SW-02
      role: AGGREGATION_SWITCH
      rack: RACK-04
      rack_unit: 20
      ports: 48

  Access层:
    - id: access-1
      name: Access-SW-01
      role: ACCESS_SWITCH
      rack: RACK-05
      rack_unit: 10
      ports: 24
    
    - id: access-2
      name: Access-SW-02
      role: ACCESS_SWITCH
      rack: RACK-06
      rack_unit: 10
      ports: 24

  Servers:
    - id: server-1
      name: Server-01
      role: SERVER
      rack: RACK-05
      rack_unit: 1
      ports: 2
    
    - id: server-2
      name: Server-02
      role: SERVER
      rack: RACK-05
      rack_unit: 2
      ports: 2

connections:
  - source: core-1
    target: agg-1
    count: 4
    link_type: UPLINK
    speed: 40000
    redundancy: true
    
  - source: core-2
    target: agg-2
    count: 4
    link_type: UPLINK
    speed: 40000
    redundancy: true
    
  - source: agg-1
    target: access-1
    count: 2
    link_type: DOWNLINK
    speed: 10000
    redundancy: true

  - source: access-1
    target: server-1
    count: 1
    link_type: ACCESS
    speed: 1000
    redundancy: false
```

## 2. 场景2：Spine-Leaf数据中心

yaml

```
name: "Spine-Leaf Data Center"
description: "现代数据中心Spine-Leaf架构"

devices:
  Spine层:
    - id: spine-1
      name: Spine-01
      role: SPINE_SWITCH
      rack: RACK-01
      rack_unit: 20
      ports: 32
    
    - id: spine-2
      name: Spine-02
      role: SPINE_SWITCH
      rack: RACK-02
      rack_unit: 20
      ports: 32
    
    - id: spine-3
      name: Spine-03
      role: SPINE_SWITCH
      rack: RACK-03
      rack_unit: 20
      ports: 32

  Leaf层:
    - id: leaf-1
      name: Leaf-01
      role: LEAF_SWITCH
      rack: RACK-04
      rack_unit: 10
      ports: 48
    
    - id: leaf-2
      name: Leaf-02
      role: LEAF_SWITCH
      rack: RACK-05
      rack_unit: 10
      ports: 48
    
    - id: leaf-3
      name: Leaf-03
      role: LEAF_SWITCH
      rack: RACK-06
      rack_unit: 10
      ports: 48

connections:
  - source: spine-1
    target: leaf-1
    count: 4
    link_type: UPLINK
    speed: 100000
    redundancy: true
    
  - source: spine-2
    target: leaf-2
    count: 4
    link_type: UPLINK
    speed: 100000
    redundancy: true
```



## 3. 场景3：安全拓扑

yaml

```
name: "Security Topology"
description: "安全网络拓扑"

devices:
  - id: router-1
    name: Edge-Router
    role: ROUTER
    rack: RACK-01
    rack_unit: 20
    ports: 8

  - id: firewall-1
    name: Firewall-Primary
    role: FIREWALL
    rack: RACK-01
    rack_unit: 15
    ports: 16

  - id: firewall-2
    name: Firewall-Secondary
    role: FIREWALL
    rack: RACK-02
    rack_unit: 15
    ports: 16

  - id: lb-1
    name: Load-Balancer
    role: LOAD_BALANCER
    rack: RACK-01
    rack_unit: 10
    ports: 8

  - id: server-1
    name: App-Server-01
    role: SERVER
    rack: RACK-03
    rack_unit: 1
    ports: 2

connections:
  - source: router-1
    target: firewall-1
    count: 2
    link_type: WAN
    speed: 10000
    redundancy: true

  - source: firewall-1
    target: lb-1
    count: 2
    link_type: WAN
    speed: 10000
    redundancy: true

  - source: lb-1
    target: server-1
    count: 1
    link_type: ACCESS
    speed: 1000
    redundancy: false
```