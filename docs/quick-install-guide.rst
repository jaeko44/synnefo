.. _quick-install-guide:

Quick Installation Guide on Debian Jessie
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This is the Synnefo Quick Installation guide.

It describes how to install the whole Synnefo stack on one (1) physical node,
in less than 10 minutes. The installation uses the snf-deploy deployment tool
and installs on a physical node that runs Debian Jessie. After successful
installation, you will have the following services running:

    * Identity Management (Astakos)
    * Object Storage Service (Pithos)
    * Compute Service (Cyclades)
    * Image Service (part of Cyclades)
    * Network Service (part of Cyclades)

and a single unified Web UI to manage them all.


Prerequisites
=============

To install Synnefo the only thing you need is a Debian Jessie Base System that
has access to the public Internet.

Installation of snf-deploy
==========================

First of all we need to install the snf-deploy tool. To do so please add the
following line in your ``/etc/apt/sources.list`` file:

.. code-block:: console

   deb http://apt.dev.grnet.gr jessie/

Then run:

.. code-block:: console

   # curl https://dev.grnet.gr/files/apt-grnetdev.pub | apt-key add -
   # apt-get update
   # apt-get install snf-deploy

Synnefo configuration & installation
====================================

Configuration
-------------

Now that you have `snf-deploy` successfully installed on your system, you can
continue with configuring and installing Synnefo. Configuration files for
snf-deploy can be found in ``/etc/snf-deploy``, the defaults should work out of
the box for most setups. If for some reason you encounter any problems, you
should check there for network conflicts, etc.

Installation
------------

To install the whole Synnefo stack run:

.. code-block:: console

   # snf-deploy synnefo --autoconf

This might take a while depending on the physical host you are running on, since
it will download everything that is necessary, install and configure the whole
stack.

If the following ends without errors, you have successfully installed Synnefo.

NOTE: All the passwords and secrets used during installation are
hardcoded in `/etc/snf-deploy/synnefo.conf`. You can change them before
starting the installation process. If you want snf-deploy create random
passwords use the ``--pass-gen`` option. The generated passwords will be
kept in the `/var/lib/snf-deploy/snf_deploy_status` file.

.. _access-synnefo:

Accessing the Synnefo installation
==================================

Remote access
-------------

If you want to access the Synnefo installation from a remote machine:

Method 1: Modify DNS name resolution
____________________________________

* Set your nameservers accordingly by adding the following line as your
  first nameserver in ``/etc/resolv.conf``:

  .. code-block:: console

     nameserver <IP>

  The **<IP>** is the public IP of the machine that you deployed Synnefo on,
  and want to access. Note that ``/etc/resolv.conf`` can be overwritten by
  other programs (``Network Manager``, ``dhclient``) and you may therefore lose
  this line. Depending on your system, you may need to disable writes to
  ``/etc/resolv.conf`` or prepend the nameservers in the
  ``/etc/dhclient.conf``.

Method 2: Modify /etc/hosts
___________________________

* Add the IP of your Synnefo installation in your ``/etc/hosts`` file:

  .. code-block:: console

      <IP> synnefo.live
      <IP> accounts.synnefo.live
      <IP> compute.synnefo.live
      <IP> pithos.synnefo.live

 If you're using Windows the same settings can be applied on
 ``C:\WINDOWS\SYSTEM32\DRIVERS\ETC\HOSTS``.

Method 3: Use a SOCKS proxy (easier)
____________________________________

* Alternatively, you can setup a SOCKS proxy using the ssh client and instruct
  your browser to use it. To setup a SOCKS proxy run:

 .. code-block:: console

    $ ssh -D localhost:9009 user@host

 Now, you can either instruct your browser to tunnel all the traffic through
 the SOCKS proxy or even better install a plugin like `Foxy Proxy
 <https://addons.mozilla.org/en-US/firefox/addon/foxyproxy-standard/>`_ to fine
 tune when to use the proxy or not.

 In order to use the proxy globally in Firefox, go to
 ``Edit->Preferences->Advanced->Network->Settings`` and set ``SOCKS host`` to
 ``localhost`` and ``Port`` to ``9009``. Firefox by default doesn't use the
 SOCKS proxy for domain name resolving. To enable this, type ``about:config`` in
 the URL bar and change ``network.proxy.socks_remote_dns`` to ``true``.

 For better control on which sites you view over the proxy, download FoxyProxy
 and set a ``URL_Pattern`` to whitelist the ``synnefo.live`` domain. To do this
 use the URL_Pattern ``*synnefo.live*`` and set FoxyProxy to run in the
 ``Use proxies based on their pre-defined patterns and priorities`` mode.

 FoxyProxy is also available for Chrome through the `Chrome Web Store
 <https://chrome.google.com/webstore/detail/foxyproxy-standard/gcknhkkoolaabfmlnjonogaaifnjlfnp?hl=en>`_,
 so a similar approach will work in Chrome also.

 .. note::

    Internet Explorer doesn't support SOCKS5 proxies.

Then open a browser and point it to:

`https://astakos.synnefo.live/astakos/ui/login`

Local access
------------

If you want to access the installation from the same machine it runs on, you
must connect graphically to the machine first. A simple way is to use SSH with
X-forwarding:

.. code-block:: console

   $ ssh <user>@<hostname> -YC

where **<user>** is your username and **<hostname>** is the IP/hostname of your
machine. Then, run ``firefox`` or ``chromium`` and in the address bar write:

`https://astakos.synnefo.live/astakos/ui/login`

The default <domain> is set to ``synnefo.live``. A local BIND is already
set up by `snf-deploy` to serve all FQDNs.

Login
-----

Once you see the Login screen, go ahead and login using:

| username: user@synnefo.org
| password: 12345

which is the default user. If you see the welcome screen, you have successfully
installed Synnefo on a single node.


Caveats
=======

Certificates
------------
To be able to view all web pages make sure you have accepted all certificates
for domains:

* synnefo.live
* accounts.synnefo.live
* cyclades.synnefo.live
* pithos.synnefo.live
* cms.synnefo.live



Using the installation
======================

You should be able to:

* Spawn VMs from the one public Image that is already registered
* Upload files on Pithos
* Create Private Networks
* Connect VMs to Private Networks
* Upload new Images
* Register the new Images
* Spawn VMs from your new Images
* Use the kamaki command line client to access the REST APIs
