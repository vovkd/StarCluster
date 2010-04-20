#!/usr/bin/env python
"""
starcluster [global-opts] action [action-opts] [<action-args> ...]
"""

__description__ = """
StarCluster - (http://web.mit.edu/starcluster)
Software Tools for Academics and Researchers (STAR)
Please submit bug reports to starcluster@mit.edu
"""

__moredoc__ = """
Each command consists of a class, which has the following properties:

- Must have a class member 'names' which is a list of the names for the command;

- Can optionally have a addopts(self, parser) method which adds options to the
  given parser. This defines command options.
"""

__version__ = "$Revision: 0.9999 $"
__author__ = "Justin Riley <justin.t.riley@gmail.com>"

import os
import sys
import time
import logging
from pprint import pprint, pformat
from starcluster import cluster
from starcluster import node
from starcluster import config
from starcluster import exception
from starcluster import static
from starcluster import optcomplete
from starcluster import image
from starcluster import volume

from starcluster.logger import log

#try:
    #import optcomplete
    #CmdComplete = optcomplete.CmdComplete
#except ImportError,e:
    #optcomplete, CmdComplete = None, object

class CmdBase(optcomplete.CmdComplete):
    parser = None
    opts = None
    gopts = None

    @property
    def goptions_dict(self):
        return dict(self.gopts.__dict__)

    @property
    def options_dict(self):
        return dict(self.opts.__dict__)

    @property
    def specified_options_dict(self):
        """ only return options with non-None value """
        specified = {}
        options = self.options_dict
        for opt in options:
            if options[opt]:
                specified[opt] = options[opt]
        return specified

    @property
    def cfg(self):
        return self.goptions_dict.get('CONFIG')

class CmdStart(CmdBase):
    """
    start [options] <cluster_template> <tagname>

    Start a new cluster 

    Example: 

        starcluster start largecluster physics
    
    This will launch a cluster tagged "physics" using the
    settings from the cluster template "largecluster" defined
    in the configuration file
    
    """
    names = ['start']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                return optcomplete.ListCompleter(cfg.get_cluster_names())
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option("-x","--no-create", dest="no_create",
            action="store_true", default=False, help="Do not launch new ec2 " + \
"instances when starting cluster (uses existing instances instead)")
        opt = parser.add_option("-v","--validate-only", dest="validate_only",
            action="store_true", default=False, help="Only validate cluster " + \
"settings, do not start a cluster")
        parser.add_option("-l","--login-master", dest="login_master",
            action="store_true", default=False, 
            help="ssh to ec2 cluster master node after launch")
        parser.add_option("-d","--description", dest="cluster_description",
            action="store", type="string", 
            default="Cluster requested at %s" % time.strftime("%Y%m%d%H%M"), 
            help="brief description of cluster")
        parser.add_option("-s","--cluster-size", dest="cluster_size",
            action="store", type="int", default=None, 
            help="number of ec2 nodes to launch")
        parser.add_option("-u","--cluster-user", dest="cluster_user",
            action="store", type="string", default=None, 
            help="name of user to create on cluster (defaults to sgeadmin)")
        opt = parser.add_option("-S","--cluster-shell", dest="cluster_shell",
            action="store", choices=static.AVAILABLE_SHELLS.keys(),
            default=None, help="shell for cluster user ")
        if optcomplete:
            opt.completer = optcomplete.ListCompleter(opt.choices)
        parser.add_option("-m","--master-image-id", dest="master_image_id",
            action="store", type="string", default=None, 
            help="image to use for master")
        parser.add_option("-n","--node-image-id", dest="node_image_id",
            action="store", type="string", default=None, 
            help="image to use for node")
        opt = parser.add_option("-I","--master-instance-type", dest="master_instance_type",
            action="store", choices=static.INSTANCE_TYPES.keys(),
            default=None, help="specify machine type for the master instance")
        opt = parser.add_option("-i","--node-instance-type", dest="node_instance_type",
            action="store", choices=static.INSTANCE_TYPES.keys(),
            default=None, help="specify machine type for the node instances")
        if optcomplete:
            opt.completer = optcomplete.ListCompleter(opt.choices)
        parser.add_option("-a","--availability-zone", dest="availability_zone",
            action="store", type="string", default=None, 
            help="availability zone to launch ec2 instances in")
        parser.add_option("-k","--keyname", dest="keyname",
            action="store", type="string", default=None, 
            help="name of AWS ssh key to use for cluster")
        parser.add_option("-K","--key-location", dest="key_location",
            action="store", type="string", default=None, metavar="FILE",
            help="path to ssh key used for this cluster")

    def execute(self, args):
        if len(args) != 2:
            self.parser.error("please specify a <cluster_template> and <tagname>")
        cfg = self.cfg
        template, tag = args
        tagdict={'cluster_tag': tag}
        scluster = cfg.get_cluster_template(template)
        scluster.update(self.specified_options_dict)
        scluster.update(tagdict)
        if cluster.cluster_exists(tag,cfg) and not self.opts.no_create:
            log.error("Cluster with tagname %s already exists." % tag)
            log.error("Either choose a different tagname, or stop the " + \
                      "existing cluster using:")
            log.error("starcluster stop %s" % tag)
            log.error("If you wish to use these existing instances anyway, " + \
                      "pass --no-create to the start action")
            sys.exit(1)
        #from starcluster.utils import ipy_shell; ipy_shell();
        log.info("Validating cluster settings...")
        if scluster.is_valid():
            log.info('Cluster settings are valid')
            if not self.opts.validate_only:
                scluster.start(create=not self.opts.no_create)
                if self.opts.login_master:
                    cluster.ssh_to_master(tag, self.cfg)
        else:
            log.error('the cluster settings provided are not valid')

class CmdStop(CmdBase):
    """
    stop <cluster>

    Shutdown a running cluster

    Example:

        starcluster stop physics

    This will stop a currently running cluster tagged "physics"
    """
    names = ['stop']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                clusters = cluster.get_cluster_security_groups(cfg)
                completion_list = [sg.name.replace(static.SECURITY_GROUP_PREFIX+'-','') for sg in clusters]
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)
                
    def addopts(self, parser):
        opt = parser.add_option("-c","--confirm", dest="confirm", 
                                action="store_true", default=False, 
                                help="Do not prompt for confirmation, " + \
                                "just shutdown the cluster")

    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster")
        cfg = self.cfg
        for cluster_name in args:
            cl = cluster.get_cluster(cluster_name,cfg)
            if not self.opts.confirm:
                resp = raw_input("Shutdown cluster %s (y/n)? " % cluster_name)
                if resp not in ['y','Y', 'yes']:
                    log.info("Aborting...")
                    continue
            cluster.stop_cluster(cluster_name, cfg)

class CmdSshMaster(CmdBase):
    """
    sshmaster <cluster>

    SSH to a cluster's master node

    e.g.

    sshmaster mycluster # ssh's to mycluster master node
    """
    names = ['sshmaster']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                clusters = cluster.get_cluster_security_groups(cfg)
                completion_list = [sg.name.replace(static.SECURITY_GROUP_PREFIX+'-','') for sg in clusters]
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option("-u","--user", dest="USER", action="store", 
                                type="string", default='root', 
                                help="login as USER (defaults to root)")

    def execute(self, args):
        if not args:
            self.parser.error("please specify a cluster")
        for arg in args:
            cluster.ssh_to_master(arg, self.cfg, user=self.opts.USER)

class CmdSshNode(CmdBase):
    """
    sshnode <cluster> <node>

    SSH to a cluster node

    e.g.

    sshnode mycluster master #ssh's to mycluster master
    sshnode mycluster node001 #ssh's to mycluster node001

    or in shorthand:

    sshnode mycluster 0 #ssh's to mycluster master
    sshnode mycluster 1 #ssh's to mycluster node001
    """
    names = ['sshnode']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                clusters = cluster.get_cluster_security_groups(cfg)
                completion_list = [sg.name.replace(static.SECURITY_GROUP_PREFIX+'-','') for sg in clusters]
                max_num_nodes = 0
                for scluster in clusters:
                    num_instances = len(scluster.instances())
                    if num_instances > max_num_nodes:
                        max_num_nodes = num_instances
                completion_list.extend(['master'])
                completion_list.extend([str(i) for i in range(0,num_instances)])
                completion_list.extend(["node%03d" % i for i in range(1,num_instances)])
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                print e
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option("-u","--user", dest="USER", action="store",
                                type="string", default='root', 
                                help="login as USER (defaults to root)")

    def execute(self, args):
        if not args or len(args) < 1:
            self.parser.error("please specify a cluster and node to connect to")
        scluster = args[0]
        ids = args[1:]
        for id in ids:
            cluster.ssh_to_cluster_node(scluster, id, self.cfg,
                                        user=self.opts.USER)

class CmdSshInstance(CmdBase):
    """
    sshintance <instance-id>

    SSH to an EC2 instance

    e.g.

    sshinstance ec2-123-123-123-12.compute-1.amazonaws.com 
    
    sshinstance i-14e9157c
    """
    names = ['sshinstance']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                ec2 = cfg.get_easy_ec2()
                instances = ec2.get_all_instances()
                completion_list = [i.id for i in instances]
                completion_list.extend([i.dns_name for i in instances])
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option("-u","--user", dest="USER", action="store", 
                                type="string", default='root', 
                                help="login as USER (defaults to root)")

    def execute(self, args):
        if not args:
            self.parser.error(
                "please specify an instance id or dns name to connect to")
        for arg in args:
            # user specified dns name or instance id
            instance = args[0]
            node.ssh_to_node(instance, self.cfg, user=self.opts.USER)

class CmdListClusters(CmdBase):
    """
    listclusters 

    List all active clusters
    """
    names = ['listclusters']
    def execute(self, args):
        cfg = self.cfg
        cluster.list_clusters(cfg)

class CmdCreateImage(CmdBase):
    """
    createimage [options] <instance-id> <image_name> <bucket> 

    Create a new image (AMI) from a currently running EC2 instance

    Example:

        starcluster createimage i-999999 my-new-image mybucket

    NOTE: It is recommended not to create a new StarCluster AMI from
    an instance launched by StarCluster. Rather, launch a single 
    StarCluster instance using elasticfox or the EC2 API tools, modify
    it how you like, and then use this command to create a new AMI from 
    the running instance.
    """
    names = ['createimage']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                ec2 = cfg.get_easy_ec2()
                instances = ec2.get_all_instances()
                completion_list = [i.id for i in instances]
                completion_list.extend([i.dns_name for i in instances])
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def addopts(self, parser):
        opt = parser.add_option(
            "-r","--remove-image-files", dest="remove_image_files",
            action="store_true", default=False, 
            help="Remove generated image files on the instance after registering")

    def execute(self, args):
        if len(args) != 3:
            self.parser.error('you must specify an instance-id, image name, and bucket')
        instanceid, image_name, bucket = args
        cfg = self.cfg
        ami_id = image.create_image(instanceid, image_name, bucket, cfg,
                           **self.specified_options_dict)
        log.info("Your new AMI id is: %s" % ami_id)

class CmdCreateVolume(CmdBase):
    """
    createvolume [options] <volume_size> <volume_zone>

    Create a new EBS volume for use with StarCluster
    """

    names = ['createvolume']

    def addopts(self, parser):
        opt = parser.add_option(
            "-i","--image-id", dest="image_id",
            action="store", type="string", default=None,
            help="Use image_id AMI when launching volume host instance")
        opt = parser.add_option(
            "-n","--no-shutdown", dest="shutdown_instance",
            action="store_false", default=True,
            help="Detach volume and shutdown instance after creating volume")
        opt = parser.add_option(
            "-a","--add-to-config", dest="add_to_cfg",
            action="store_true", default=False,
            help="Add a new volume section to the config after creating volume")
    def execute(self, args):
        if len(args) != 2:
            self.parser.error("you must specify a size (in GB) and an availability zone")
        size, zone = args
        vc = volume.VolumeCreator(self.cfg, **self.specified_options_dict)
        volid = vc.create(size, zone)
        log.info("Your new %dGB volume %s has been created successfully" % \
                 (size,volid))

class CmdListZones(CmdBase):
    """
    listzones

    List all EC2 availability zones
    """
    names = ['listzones']
    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_zones()

class CmdListImages(CmdBase):
    """
    listimages

    List all registered EC2 images (AMIs)
    """
    names = ['listimages']

    def addopts(self, parser):
        opt = parser.add_option(
            "-x","--executable-by-me", dest="executable",
            action="store_true", default=False,
            help="Show images that you have permission to execute")

    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        if self.opts.executable:
            ec2.list_executable_images()
        else:
            ec2.list_registered_images()

class CmdListBuckets(CmdBase):
    """
    listbuckets

    List all S3 buckets
    """
    names = ['listbuckets']
    def execute(self, args):
        s3 = self.cfg.get_easy_s3()
        buckets = s3.list_buckets()

class CmdShowImage(CmdBase):
    """
    showimage <image_id>

    Show all AMI parts and manifest files on S3 for an EC2 image (AMI)

    Example:

        starcluster showimage ami-999999
    """
    names = ['showimage']
    def execute(self, args):
        if not args:
            self.parser.error('please specify an AMI id')
        ec2 = self.cfg.get_easy_ec2()
        for arg in args:
            ec2.list_image_files(arg)
   
class CmdShowBucket(CmdBase):
    """
    showbucket <bucket>

    Show all files in an S3 bucket
    """
    names = ['showbucket']
    def execute(self, args):
        if not args:
            self.parser.error('please specify an S3 bucket')
        for arg in args:
            s3 = self.cfg.get_easy_s3()
            bucket = s3.list_bucket(arg)

class CmdRemoveVolume(CmdBase):
    """
    removevolume <volume_id> 

    Delete one or more EBS volumes

    WARNING: This command *permanently* removes an EBS volume.
    Be careful!

    Example:

        removevolume vol-999999
    """
    names = ['removevolume']

    def execute(self, args):
        if not args:
            self.parser.error("no volumes specified. exiting...")
        for arg in args:
            volid = arg
            ec2 = self.cfg.get_easy_ec2()
            vol = ec2.get_volume(volid)
            if vol.status in ['attaching', 'in-use']:
                log.error("volume is currently in use. aborting...")
                return
            if vol.status == 'detaching':
                log.error("volume is currently detaching. " + \
                          "please wait a few moments and try again...")
                return
            resp = raw_input("**PERMANENTLY** delete %s (y/n)? " % volid)
            if resp not in ['y','Y', 'yes']:
                log.info("Aborting...")
                return
            if vol.delete():
                log.info("Volume %s deleted successfully" % vol.id)
            else:
                log.error("Error deleting volume %s" % vol.id)

class CmdRemoveImage(CmdBase):
    """
    removeami [options] <imageid> 

    Deregister an EC2 image (AMI) and remove it from S3

    WARNING: This command *permanently* removes an AMI from 
    EC2/S3 including all AMI parts and manifest. Be careful!

    Example:

        removeami ami-999999
    """
    names = ['removeimage']

    def addopts(self, parser):
        parser.add_option("-p","--pretend", dest="PRETEND", action="store_true",
            default=False,
            help="pretend run, dont actually remove anything")
        parser.add_option("-c","--confirm", dest="CONFIRM", action="store_true",
            default=False,
            help="do not prompt for confirmation, just remove the image")

    def execute(self, args):
        if not args:
            self.parser.error("no images specified. exiting...")
        for arg in args:
            imageid = arg
            ec2 = self.cfg.get_easy_ec2()
            image = ec2.get_image(imageid)
            confirmed = self.opts.CONFIRM
            pretend = self.opts.PRETEND
            if not confirmed:
                if not pretend:
                    resp = raw_input("**PERMANENTLY** delete %s (y/n)? " % imageid)
                    if resp not in ['y','Y', 'yes']:
                        log.info("Aborting...")
                        return
            ec2.remove_image(imageid, pretend=pretend)

class CmdListInstances(CmdBase):
    """
    listinstances

    List all running EC2 instances
    """
    names = ['listinstances']

    def addopts(self, parser):
        parser.add_option("-t","--show-terminated", dest="show_terminated", action="store_true",
            default=False,
            help="show terminated instances") 

    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_all_instances(self.opts.show_terminated)

class CmdShowConsole(CmdBase):
    """
    showconsole <instance-id>

    Show console output for an EC2 instance

    Example:

        showconsole i-999999

    This will print out the startup logs for instance 
    i-999999
    """
    names = ['showconsole']

    @property
    def completer(self):
        if optcomplete:
            try:
                cfg = config.StarClusterConfig()
                cfg.load()
                ec2 = cfg.get_easy_ec2()
                instances = ec2.get_all_instances()
                completion_list = [i.id for i in instances]
                return optcomplete.ListCompleter(completion_list)
            except Exception, e:
                log.error('something went wrong fix me: %s' % e)

    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        if args:
            instance = ec2.get_instance(args[0])
            import string
            if instance:
                print ''.join([c for c in instance.get_console_output().output
                               if c in string.printable])
            else:
                log.error("instance does not exist")
                sys.exit(1)
        else:
            self.parser.parse_args(['--help'])

class CmdListVolumes(CmdBase):
    """
    listvolumes

    List all EBS volumes
    """
    names = ['listvolumes']
    def execute(self, args):
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_volumes()

class CmdListPublic(CmdBase):
    """
    listpublic

    List all public StarCluster images on EC2
    """
    names = ['listpublic']
    def execute(self, args):
        log.info("Listing all public StarCluster images...\n")
        ec2 = self.cfg.get_easy_ec2()
        ec2.list_starcluster_public_images()

class CmdRunPlugin(CmdBase):
    """
    runplugin <plugin_name> <cluster_tag>

    Run a StarCluster plugin on a runnning cluster

    plugin_name - name of plugin section defined in the config
    cluster_tag - tag name of a running StarCluster

    e.g.

    runplugin myplugin physicscluster
    """
    names = ['runplugin']
    def execute(self,args):
        if len(args) != 2:
            self.parser.error("Please provide a plugin_name and <cluster_tag>")
        plugin_name, cluster_tag = args
        cluster.run_plugin(plugin_name, cluster_tag, self.cfg)

class CmdShell(CmdBase):
    """
    shell

    Load interactive ipython shell for starcluster development
    
    The following objects are automatically available at the prompt:

        cfg - starcluster.config.StarClusterConfig instance
        ec2 - starcluster.awsutils.EasyEC2 instance
        s3 - starcluster.awsutils.EasyS3 instance
    """
    names = ['shell']
    def execute(self,args):
        cfg = self.cfg
        ec2 = cfg.get_easy_ec2()
        s3 = ec2.s3
        from starcluster.utils import ipy_shell; ipy_shell();

class CmdHelp:
    """
    help

    Show StarCluster usage
    """
    names =['help']
    def execute(self, args):
        import optparse
        if args:
            cmdname = args[0]
            try:
                sc = subcmds_map[cmdname]
                lparser = optparse.OptionParser(sc.__doc__.strip())
                if hasattr(sc, 'addopts'):
                    sc.addopts(lparser)
                lparser.print_help()
            except KeyError:
                raise SystemExit("Error: invalid command '%s'" % cmdname)
        else:
            gparser.parse_args(['--help'])

def get_description():
    return __description__.replace('\n','',1)

def parse_subcommands(gparser, subcmds):

    """Parse given global arguments, find subcommand from given list of
    subcommand objects, parse local arguments and return a tuple of global
    options, selected command object, command options, and command arguments.
    Call execute() on the command object to run. The command object has members
    'gopts' and 'opts' set for global and command options respectively, you
    don't need to call execute with those but you could if you wanted to."""

    import optparse
    global subcmds_map # needed for help command only.

    print get_description()

    # Build map of name -> command and docstring.
    subcmds_map = {}
    gparser.usage += '\n\nAvailable Actions\n'
    for sc in subcmds:
        helptxt = sc.__doc__.splitlines()[3].strip()
        gparser.usage += '- %s: %s\n' % (', '.join(sc.names),
                                       helptxt)
        for n in sc.names:
            assert n not in subcmds_map
            subcmds_map[n] = sc

    # Declare and parse global options.
    gparser.disable_interspersed_args()

    gopts, args = gparser.parse_args()
    if not args:
        gparser.print_help()
        raise SystemExit("\nError: you must specify an action.")
    subcmdname, subargs = args[0], args[1:]

    # load StarClusterConfig into global options
    try:
        cfg = config.StarClusterConfig(gopts.CONFIG)
        cfg.load()
    except exception.ConfigNotFound,e:
        log.error(e.msg)
        e.display_options()
        sys.exit(1)
    except exception.ConfigError,e:
        log.error(e.msg)
        sys.exit(1)
    gopts.CONFIG = cfg

    # Parse command arguments and invoke command.
    try:
        sc = subcmds_map[subcmdname]
        lparser = optparse.OptionParser(sc.__doc__.strip())
        if hasattr(sc, 'addopts'):
            sc.addopts(lparser)
        sc.parser = lparser
        sc.gopts = gopts
        sc.opts, subsubargs = lparser.parse_args(subargs)
    except KeyError:
        raise SystemExit("Error: invalid command '%s'" % subcmdname)

    return gopts, sc, sc.opts, subsubargs

def main():
    # Create global options parser.
    global gparser # only need for 'help' command (optional)
    import optparse
    gparser = optparse.OptionParser(__doc__.strip(), version=__version__)
    gparser.add_option("-d","--debug", dest="DEBUG", action="store_true",
        default=False,
        help="print debug messages (useful for diagnosing problems)")
    gparser.add_option("-c","--config", dest="CONFIG", action="store",
        metavar="FILE",
        help="use alternate config file (default: ~/.starclustercfg)")

    # Declare subcommands.
    subcmds = [
        CmdStart(),
        CmdStop(),
        CmdListClusters(),
        CmdSshMaster(),
        CmdSshNode(),
        CmdSshInstance(),
        CmdListInstances(),
        CmdListImages(),
        CmdShowImage(),
        CmdCreateImage(),
        CmdRemoveImage(),
        CmdListBuckets(),
        CmdShowBucket(),
        CmdCreateVolume(),
        CmdListVolumes(),
        CmdRemoveVolume(),
        CmdShowConsole(),
        CmdListZones(),
        CmdListPublic(),
        CmdShell(),
        CmdHelp(),
    ]

    # subcommand completions
    scmap = {}
    for sc in subcmds:
        for n in sc.names:
            scmap[n] = sc
  
    if optcomplete:
        listcter = optcomplete.ListCompleter(scmap.keys())
        subcter = optcomplete.NoneCompleter()
        optcomplete.autocomplete(
            gparser, listcter, None, subcter, subcommands=scmap)
    elif 'COMP_LINE' in os.environ:
        return -1

    gopts, sc, opts, args = parse_subcommands(gparser, subcmds)
    if gopts.DEBUG:
        log.setLevel(logging.DEBUG)
    if args and args[0] =='help':
        sc.parser.print_help()
        sys.exit(0)
    try:
        sc.execute(args)
    except exception.BaseException,e:
        log.error(e.msg)
        sys.exit(1)

def test():
    pass

if os.environ.has_key('starcluster_commands_test'):
    test()
elif __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print "Interrupted, exiting."
