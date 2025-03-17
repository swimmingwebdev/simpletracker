#!/bin/bash

echo "Removing Kafka meta.properties file"
find ./data/kafka/kafka-logs -name "meta.properties" -exec rm -f {} \;

