#!/usr/bin/env python

"""
    detect-thread.py
    
    Run `darknet` over stream of images
"""

import os
import sys
import numpy as np
from time import sleep
import argparse
from time import time
from PIL import Image

from multiprocessing import Process, Queue
from Queue import Empty

from detector import Darknet_ObjectDetector as ObjectDetector
from detector import DetBBox, format_image

defaults = {
    "name_path" : '/home/bjohnson/projects/darknet-bkj/custom-tools/pfr-data.bak/custom.names',
    "cfg_path" : '/home/bjohnson/projects/darknet-bkj/custom-tools/pfr-data.bak/yolo-custom.cfg',
    "weight_path" : '/home/bjohnson/projects/darknet-bkj/custom-tools/pfr-data.bak/backup/yolo-custom_10000.weights',
}

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name-path', type=str, default=defaults['name_path'])
    parser.add_argument('--cfg-path', type=str, default=defaults['cfg_path'])
    parser.add_argument('--weight-path', type=str, default=defaults['weight_path'])
    parser.add_argument('--thresh', type=float, default=0.1)
    parser.add_argument('--nms', type=float, default=0.3)
    parser.add_argument('--n-threads', type=int, default=10)
    parser.add_argument('--draw', action='store_true')
    return parser.parse_args()


def prep_images(in_, out_, det):
    while True:
        try:
            im_name = in_.get(timeout=5)
            try:
                pil_image = Image.open(im_name)
                out_.put((im_name, format_image(pil_image)))
            except KeyboardInterrupt:
                raise
            except:
                print >> sys.stderr, "Error: Cannot load @ %s" % im_name
        
        except KeyboardInterrupt:
            raise
        
        except Empty:
            return


def read_stdin(gen, out_):
    for line in gen:
        line = line.strip()
        out_.put(line)


if __name__ == "__main__":
    args = parse_args()
    
    ObjectDetector.set_device(0)
    det = ObjectDetector(args.cfg_path, args.weight_path, args.thresh, args.nms, int(args.draw))
    
    class_names = open(args.name_path).read().splitlines()
    print >> sys.stderr, "class_names = %s" % "\t".join(class_names)
    
    # Thread to read from std
    filenames = Queue()
    newstdin = os.fdopen(os.dup(sys.stdin.fileno()))
    stdin_reader = Process(target=read_stdin, args=(newstdin, filenames))
    stdin_reader.start()
    
    # Thread to load images    
    processed_images = Queue()
    image_processors = [Process(target=prep_images, args=(filenames, processed_images, det)) for _ in range(args.n_threads)]
    for image_processor in image_processors:
        image_processor.start()
    
    i = 0
    start = time()
    c_load_time, c_pred_time = 0, 0
    while True:
        py_all_time = time() - start
        py_load_time = py_all_time - c_load_time - c_pred_time
        i += 1
        
        if not i % 1:
            print >> sys.stderr, "%d | pyall %f | pyload %f | cload %f | cpred %f" % (i, py_all_time, py_load_time, c_load_time, c_pred_time)
        
        try:
            im_name, img = processed_images.get(timeout=5)
            detections, load_time, pred_time = det.detect_object(*img)
            c_load_time += load_time
            c_pred_time += pred_time
            
            for bbox in detections:
                class_name = class_names[bbox.cls]
                res = [im_name, class_name, bbox.confidence, bbox.top, bbox.left, bbox.bottom, bbox.right]
                print '\t'.join(map(str, res))
                sys.stdout.flush()
        
        except KeyboardInterrupt:
            raise
        
        except Empty:
            os._exit(0)
        
        except:
            pass