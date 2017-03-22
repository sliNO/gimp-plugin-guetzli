# -*- coding: utf-8 -*-
# License: MIT License

import glob
import json
import locale
import os
import subprocess
from collections import OrderedDict
import threading
from decimal import Decimal

try:
    from gimpfu import *
    isGIMP = True
except ImportError:
    isGIMP = False


class ProgressBar(object):
    def __init__(self, step=0.01):
        """
            self.step calcation
        """
        self.value = Decimal(0)
        self._step = Decimal(step)
        # <blockquote cite="https://developer.gimp.org/api/2.0/libgimp/libgimp-gimpprogress.html">
        # gimp_progress_update
        # percentage :Percentage of progress completed (in the range from 0.0 to 1.0).
        # </blockquote>
        self.minimum = Decimal(0)
        self.maximum = Decimal(1)
        # todo model&view split
        if isGIMP:
            gimp.progress_init("Save guetzli ...")
    @property
    def step(self):
        return self._step
    @step.setter
    def step(self, value):
        self._step = value
    def perform_step(self):
        """
            value increment
        :return: None
        """
        self.value += self.step
        if isGIMP:
            gimp.progress_update(self.value)
        else:
            print(self.value)
        if self.value >= self.maximum:
            self.value = self.minimum

class Canvas(object):
    """
        Image Wrapper Class
    """
    def __init__(self):
        if isGIMP:
            self.image = gimp.image_list()[0]
        else:
            self.image = None
    @property
    def filename(self):
        if self.image is not None:
            return self.image.filename
        return '.\\test.png'
    @property
    def width(self):
        if self.image is not None:
            return self.image.width
        return 800
    @property
    def height(self):
        if self.image is not None:
            return self.image.height
        return 617
    @property
    def size(self):
        return self.width * self.height
class Plugin(object):
    JSON = None

    def __init__(self):
        self.base_dir = os.path.dirname(__file__)
        Plugin.load_setting()
        node = Plugin.JSON['COMMAND']
        self.cmd = self.search_command(node['FILE'])
        self.params = OrderedDict()
        self.is_verbose = node['PARAMS']['-verbose'].upper() == 'TRUE'
        self.is_new_shell = node['NEW_SHELL'].upper() == 'TRUE'
        self.output_extension = '.jpeg'
        self.canvas = Canvas()
        self.input_file = None
        self.output_file = None
    def search_command(self, node):
        """ search guetzli
        :param node:
        :return:file name
                order by find first
        """
        target = node['PREFIX']
        lower_limit = int(node['LOWER_LIMIT'])
        link = node['DOWNLOAD']['LINK']
        #if isGIMP:
        #    gimp.message("INFO:" + link)
            #raise Exception('File Not Found\n{0}\nPlease download {1}\n{2}'.format(self.base_dir, target[:-1], link))
        for exe_file in glob.glob(os.path.join(self.base_dir, target)):
            # skip plugin file
            if os.path.getsize(exe_file) >= lower_limit:
                return exe_file
        raise Exception('File Not Found\n{0}\nPlease download {1}\n{2}'.format(self.base_dir, target[:-1], link))

    @staticmethod
    def load_setting():
        """
        load json
        :return:json data
        """
        if Plugin.JSON is None:
            # .py => .json
            file_name = Plugin.with_suffix(__file__, '.json')
            try:
                with open(file_name, 'r') as infile:
                    Plugin.JSON = json.load(infile)
            except:
                # file open error Wrapping
                raise Exception('File Not Found\n{0}'.format(file_name))
        return Plugin.JSON

    @staticmethod
    def with_suffix(file_name, suffix):
        return os.path.splitext(file_name)[0] + suffix
    def set_quality(self, quality):
        self.params['-quality'] = int(quality)
        return self
    def set_extension(self, extension):
        self.output_extension = extension
        return self
    def get_args(self):
        """
            guetzli , params , in , out
        :return:
        """
        args = [self.cmd]
        # add command line parameter
        for k in self.params.keys():
            args.append(k)
            args.append(str(self.params[k]))
        if self.is_verbose:
            args.append('-verbose')
        self.set_filename()
        args.append(self.input_file)
        args.append(self.output_file)
        return args
    def calc_best_step(self):
        """
          ProgressBar step calc
          <blockquote cite="https://github.com/google/guetzli">
          Guetzli uses a significant amount of CPU time. You should count on using about 1 minute of CPU per 1 MPix of input image.
          </blockquote>
        :return:
        """
        minute = Decimal(self.canvas.size) / Decimal(1000000)
        # Thread#join timeout elapsed
        step = minute / Decimal(60)
        return step
    def run(self):
        cmd = self.get_args()
        if not isGIMP:
            print(' '.join(cmd))
        cmd = u' '.join(cmd)
        # fix: python 2.7 unicode file bug
        # http://stackoverflow.com/questions/9941064/subprocess-popen-with-a-unicode-path
        cmd = cmd.encode(locale.getpreferredencoding())
        try:
            progress = ProgressBar(self.calc_best_step())
            lock = threading.RLock()
            in_params = [cmd, self.is_new_shell]
            out_params = [None, '']
            t = threading.Thread(target=Plugin.run_thread, args=(in_params, lock, out_params))
            t.start()
            while t.is_alive():
                t.join(timeout=1)
                progress.perform_step()
            with lock:
                # not Success
                if out_params[0] != 0:
                    raise Exception(out_params[1])
        except Exception as ex:
            raise
    @staticmethod
    def run_thread(in_params, lock, out_params):
        """
        :param in_params: cmd , is_new_shell
        :param lock:
        :param out_params: return code , message
        :return:None
        """
        exception = None
        try:
            return_code = subprocess.call(in_params[0], shell=in_params[1])
        except Exception as ex:
            return_code = 1
            exception = ex
        with lock:
            out_params[0] = return_code
            if exception is not None:
                out_params[1] = exception

    def set_filename(self):
        """
            set input, output file
        """
        name = self.canvas.filename
        # suffix check
        supported = tuple(Plugin.JSON['COMMAND']['SUFFIX'])
        if not name.endswith(supported):
            raise Exception('UnSupported File Type\n{0}'.format(name))
        self.input_file = '"{0}"'.format(name)
        self.output_file = '"{0}"'.format(Plugin.with_suffix(name, self.output_extension))

    @staticmethod
    def main(ext, quality):
        """
        plugin entry point
        :param ext: output file extension
        :param quality:
        :return:
        """
        plugin = Plugin()
        plugin.set_extension(ext)
        plugin.set_quality(quality)
        plugin.run()


if isGIMP:
    register(
        proc_name="python_fu_guetzli_export",
        blurb="Please click the OK button\n after saving the image",
        help="",
        author="umyu",
        copyright="umyu",
        date="2017/3/20",
        label="Save guetzli ...",
        imagetypes="*",
        params=[
            (PF_STRING, "extension", "File extension", '.jpeg'),
            (PF_SLIDER, "quality", "quality", 95, (85, 100, 1)),
        ],
        results=[],
        function=Plugin.main,
        menu="<Image>/File/Export/"
    )
    main()
else:
    Plugin.main('.jpeg', 95)
