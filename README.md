# Architecture

```mermaid
graph TD;
    subgraph VM1
        N1* --> Disk1[Disk]
        N1* --> Redis1[(Redis Metadata)]
    end

    Kafka[**Kafka Cluster];

    subgraph VM2
        N2* --> Disk2[Disk]
        N2* --> Redis2[(Redis Metadata)]
    end

    subgraph VM3
        N3* --> Disk3[Disk]
        N3* --> Redis3[(Redis Metadata)]
    end

    CLIENT

    K8s[K8s Ingress] <--> CLIENT;

    K8s <-.-> N1*;
    K8s <-.-> N2*;
    K8s <-.-> N3*;

    VM1 --> Kafka;
    Kafka --> VM1;
    VM2 --> Kafka;
    Kafka --> VM2;
    VM3 --> Kafka;
    Kafka --> VM3;
```

### Explanation

- *some docker image
- **replicated across all VMs, use Kafkas own redundancy solution
- Atleast once delivery
- Availability over consistency
- Conflict resolution based on timestamps which comes with the message and indicates the time received on the original server
