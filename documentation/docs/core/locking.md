# Locking

ACE is a distributed system that requires synchronization between processes. This is accomplished by using the `ace.system.locking.LockingInterface`.

## Locks

A **lock** is defined as an arbitrary string value. Typically, the value of a lock represents the name of something being locked. Once a lock is held, no other attempt to acquire the lock will succeed until it is released or the lock acquisition expires.

## Lock Ownership

Every lock is made by and assigned to a **lock owner**. An owner is defined as an arbitrary string value. Typically, an owner value is made up of some combination of properties such as host name, process, and thread ids. This allows for identifying unique threads of execution.

## Deadlocks

A lock owner can acquire multiple locks. If a lock owner attempts to acquire a lock that is already acquired by another owner, and that owner is waiting for the other to release a different lock, then a **deadlock** occurs.

When a deadlock occurs, the request must be made again later.