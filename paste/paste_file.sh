#!/bin/bash

source .env

curl -v -H "Authorization: $AUTH_TOKEN" -F "file=@$1" $URL
