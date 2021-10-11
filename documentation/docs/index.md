# Analysis Correlation Engine

If you're looking to just try this out, just down to the [quick start guide]() on this page to see what this system is capable of.

If you're an analyst and you want to add something new to ACE, then [look here.]()

## The Somewhat Long-winded Description of ACE

The Analysis Correlation Engine (ACE) is a recursive analysis engine geared towards cyber security. You submit stuff, the stuff you submit gets analyzed, and then you get a result back.

Most of the time there are already certain things you know about what you're submitting. You've probably already **analyzed** the thing you're submitting, and as part of that **analysis**, you've made some **observations**.

In ACE we take that idea and build on it, and we give names to specific parts of the idea.

The "thing" we're submitting is called a **Root Analysis**. It's essentially a container for all the stuff we want to analyze.

All the things we've already observed that we understand we identify as **Observables**. Each observable has a type (such as username, ip address, or file name), a value, and maybe a time recorded for the observation.

And then, naturally, that thing you observed has be analyzed. When you analyze something, you produce some kind of a result, or at least draw some kind of a conclusion. Usually you're trying to answer a question you need to have answered before you can move on to the next thing. For example, if you have observed an ip address in your environment, you might want to answer the question of "Does this IP address exist in that list of IP addresses my intelligence team gave me last week?"

We call the output of analyzing an observable an **Analysis**. And then, as a part of doing this additional analysis, you might make more observations. For example, you might actually find that the ip address was actually in that list you were looking at, so you would say that you have observed a suspect ip address interacting with your environment. In ACE, an **Analysis** can produce additional **Observables**, which can also be analyzed.

The next step would be to search in all of your logs for any occurrence of this ip address to see if anyone in your environment interacted with it around the time the original observation was made. If you found something, say a user browsed to a site hosted on the ip address through your corporate proxy, then you might want to spend your precious time on **that**!

In ACE we would add a **Detection** to the observation of the url that was used to access the suspect site hosted on the suspect ip address.

And then any **Root Analysis** with at least one **Detection** ends up turning into an **Alert** that gets sent to an **Alert Management System** analysts can use to really dive into the details of what happened.

## TL;DR

ACE defines very basic data types which it uses to recursively analyze data. *Something* is submitted to ACE for analysis. We call this *something* a **Root Analysis**. **Observations** are made on the **analysis**. Those observations are also analyzed producing additional analysis until all observations are analyzed. Analysis is performed by **analysis modules**. An **alert** is created by adding a **detection** to an observation or analysis. Alerts are submitted to an **alert management system** for review.

ACE uses free-form JSON data structures to represent the results of analysis.

## Why ACE?

Good question. There's a lot of stuff in the cyber security world that you can use for this. Here are some of the strengths and weaknesses of this one.

### Strengths

- Alert enrichment: ACE can be used to enrich existing alert data, hopefully cutting down the time it takes an analyst to come to a conclusion on any given alert.
- Detection: The same engine that enriches alerts can also be used as a generic detection engine. Throw stuff at it that you're not sure about, it'll alert if it finds something.
- Email Scanning: ACE has special support built-in for scanning your corporate email as it's delivered to your user's mailboxes. This gives you a real shot at stopping some of the most popular attacks we've been seeing, without risking blocking legitimate emails.
- Extendable: ACE has be **easily** extended to add additional functionality. As a matter of fact, this was one of the primary focus points of the design of the entire system. Analysts with even basic programming skills can add new capabilities to the system without having an administrator worry about the impact to it.
- Scalable - The design of the system is super scalable. If you find you're system falling behind, you can just spin up ACE on another system and hook it up with a few commands.
- Usable - If you're an analyst, you can just use it on your own. You really don't need someone to do a full deployment for you in order to use it.
- Tooling - The tools are built with a Unix design philosophy in mind, meaning you can run ACE as part of a chain of commands tied together with pipes.

### Weaknesses

- Like nobody is using it yet.
- Only a few people support it so far.
- You need someone with some decent IT skills to run it for a team. It's not a point-and-click kind of thing.
- You probably still need to build all the integration with all the random stuff your company runs that this project probably doesn't support yet. But if you do that, maybe consider joining the project!

## Quick Start

```python
#
# let's analyze something right now
#
# requires python3.9
python3.9 -m venv .venv
source .venv/bin/activate

# this installs everything at once
pip install ace-ecosystem[all]

# install the packages we know about
# this connects to our public github page and gets the list of all the known packages
# it can also use the env var ACE_PACKAGE_URI to get a different custom list
acecli package install --all

# now analyze that suspicious file your boss's boss sent your boss who sent it to you
acecli analyze file email_attachment.doc

# or a URL
acecli analyze url http://bit.ly/blahblah

# or an IP (v4) address
acecli analyze ipv4 8.8.4.4 
```

## Advanced Usage

```python
# 
# here's some more stuff you can do
#
# we could install packages manually
# directly from github
acecli package install ace2 package install git@github.com:ace-ecosystem/ace2-modules.git
# or from a url
acecli package install ace2 package install http://someserver.com/ace2-package.zip
# or from a local zip file you downloaded with curl
acecli package install ace2 package install /path/to/ace2-package.zip

# make sure all the packages are up to date
# this also updates all the modules
acecli package update

# could also do this to just update modules (signatures and such)
# for the ones that support it
acecli module update

# now I can see what packages I have installed
acecli package list

# and even see what modules I have available
# from all the packages I have installed
acecli module list

# and what services I can start
acecli service list

#
# PARTICIPATING IN A CORE
#

# a little more advanced usage here

# specify the core to connect to
export ACE_URI="https://ace2.local/"
export ACE_API_KEY="6a36ffce-507e-469f-8d68-39ca00fa9ccb"

# attach all the modules we have on this system to the remote core
# and start processing requests
# this is an example of how to scale (manually anyways)
acecli service start manager

#
# REMOTE USAGE OF A CORE
#

# now this command uses the remote core
# since we have our env vars set up
acecli analyze ipv4 3.127.0.4

# this lists the analysis modules of the remote core
acecli module list

#
# PRODUCTION COMMANDS
# 

# start a production core system
docker-compose -f ace2-core.yml

# start containers that run the modules
docker-compose -f ace2-modules.yml

# more to come as development continues...
```
