#!/bin/bash

cd "${TR_TORRENT_DIR}/${TR_TORRENT_NAME}" || exit
unrar e -o- ./*.rar
