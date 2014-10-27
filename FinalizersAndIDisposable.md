<!-- !b
kind: post
service: blogger
title: C# Finalizers and IDisposable
url: http://blog.adamkemp.com/2014/10/c-finalizers-and-idisposable.html
labels: C#, IDisposable, finalizer, unmanaged
blog: 6425054342484936402
draft: False
id: 8234009671753049633
-->

Because C# is a garbage collected language you can usually just allow objects to be collected whenever the system gets around to it. However, sometimes you have resources that come from outside the garbage collected world ("unmanaged resources"), and you may want to be more proactive about freeing these resources. C# provides two mechanisms for dealing with unmanaged resources: finalizers and `IDisposable`.

<!--more-->

[TOC]

Finalizers
==========

A finalizer is a function that is called on an object when it has been marked as a candidate for collection. That is, this method is called only after the GC decides that the object is no longer in use. The job of the finalizer is to free any unmanaged resources that that GC would not know how to release. In C# the finalizer is written like a constructor with a `~` in front of the class name, like this:

    :::csharp
    ~ClassName()
    {
        // Free unmanaged resources
    }

Due to their syntax there is a lot of confusion about finalizers, especially among people who come from the world of C++. They try to use finalizers to avoid the kinds of memory leaks described above. This confusion leads to code like this:

    :::csharp
    public class EventHandler
    {
        private readonly EventSource _source;

        public EventHandler(EventSource source)
        {
            _source = source;
            source.Event += HandleEvent;
        }

        ~EventHandler()
        {
            // WRONG!
            _source.Event -= HandleEvent;
        }

        private void HandleEvent(object sender, EventArgs e)
        {
            // Do something
        }
    }

Here we are attempting to use a finalizer to detach the event handler. This code is wrong on two levels. First, it will not prevent a leak. That is because finalizers don't work that way. The C# language designers unfortunately chose a syntax for finalizers that looks similar to C++ destructors, which has led to much confusion. A C# finalizer will only ever run when the object becomes a candidate for collection. In this case the object is not a candidate for collection because another object (`EventSource`) still has a reference to it. That means this code will never run, and this object will never be collected.

The second problem is that if somehow the object was a candidate for collection (maybe `EventSource` also became garbage) then this code may actually lead to undefined behavior. That is because the order in which finalizers run is undefined, and therefore the `EventSource` object may have already run its finalizer (if it has one), and therefore it may be in a state in which it should no longer be used. You should never use other managed objects in a finalizer because you don't know what state they will be in.

At best the code above is useless, and at worst it may cause crashes. Never use finalizers in this way. In fact, the _only_ reason to use a finalizer in C# is if you have unmanaged resources to clean up.

`IDisposable`
=============

Finalizers allow the garbage collector to free up unmanaged resources once an object is no longer in use, but they don't solve the problem of freeing up those resources proactively. For that we have the `IDisposable` interface. This interface is defined like so:

    :::csharp
    namespace System
    {
        public interface IDisposable
        {
            void Dispose();
        }
    }

This interface is really just used as a convention for classes that have unmanaged resources. Any class which has unmanaged resources should implement this interface, and in the `Dispose` method it should release those resources.

The `IDisposable` Pattern
=========================

It is important to remember that just because an object implements `IDisposable` doesn't mean that its resources will be freed automatically. The garbage collector never calls `Dispose` itself. Typically the code that creates an `IDisposable` object is responsible for calling `Dispose` when it is done using that object. However, a well-behaved `IDisposable` implementation will also use a finalizer to free its unmanaged resources in case `Dispose` is not called. In order to do this right you need to follow a specific pattern. That pattern looks like this:

    :::csharp
    public class UnmanagedResourceHolder : IDisposable
    {
        private bool _disposed;
        private OtherDisposableObject _otherDisposable;

        public UnmanagedResourceHolder()
        {
            AcquireUnmanagedResource();
        }

        ~UnmanagedResourceHolder()
        {
            Dispose(disposing: false);
        }

        public void Dispose()
        {
            Dispose(disposing: true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!_disposed)
            {
                _disposed = true;

                ReleaseUnmanagedResource();

                if (disposing)
                {
                    if (_otherDisposable != null)
                    {
                        _otherDisposable.Dispose();
                        _otherDisposable = null;
                    }
                }
            }
        }

        // ...
    }

Here are the key aspects of the pattern:

* Guard against multiple calls to `Dispose`. While the method should only be called once, the object should also not misbehave if it is called multiple times. In this case I used a flag (`_disposed`) to check whether it has been called before.
* Do the real work in a `protected virtual void Dispose(bool disposing)` method.
    * `virtual` so that subclasses can also do any necessary cleanup. A `sealed` class may skip this.
    * `protected` so that only this class or its subclasses can call it directly. A `sealed` class should use `private` instead.
    * The `disposing` argument tells it whether it is called from the `public void Dispose()` method or a finalizer.
* In `public void Dispose()` (the real `IDisposable` method) you should:
    * Call `Dispose(disposing: true)` to do the real work.
    * Call `GC.SuppressFinalize(this)` so that the finalizer can be skipped. This tells the GC that even though this object has a finalizer it no longer needs to be called. This is a performance optimization because any object that needs a finalizer called will have to go through an extra step that delays its ultimate collection. Suppressing that allows the object to be collected sooner.
* In the finalizer call `Dispose(disposing: false)`.
* In the `virtual void Dispose(bool disposing)` method implementation you should:
    * Check whether it has been called before. There may be other state you can use for this (such as whether some field is `null` or not), but if not then you can just add a `bool` field as I've done here.
    * If this method hasn't been called before unconditionally release all _unmanaged_ resources. That is, whether this method was called from `public void Dispose()` or from the finalizer you should _always_ release the unmanaged resources.
    * If and only if `disposing` is `true` you should _also_ call `Dispose()` on any `IDisposable` fields that this object owns and `null` out those fields.

That last bullet requires a bit more explanation. Recall from the previous section about finalizers that the order in which finalizers are called is unspecified. Let's say that you have a graph of `IDisposable` objects: `A` points to `B` and `C`, and `C` points to `D`. Further, let's say that none of these objects had their `Dispose()` method called so they will all have their finalizer called by the GC. You might think that `A`'s finalizer would be called first, and that it could then safely call `Dispose` on `B` and `C`, which would then in turn call `Disposed` on `D`. However, in reality the order in which these objects is finalized is not known. The GC can't tell which order you would want so it doesn't bother. That means `D` might be finalized first, then `C`, then `B`, and then `A`. What would happen, then, if `A` tried to _use_ `B` or `C` while it is being finalized? It could throw, which would be a bad thing to do in a finalizer.

The consequence of this is that you should _only_ release _unmanaged_ resources in a finalizer and avoid using any other objects or fields. Don't call any methods on other objects (including `Dispose`). At this point every object is on its own to clean up its unmanaged resources in its own finalizer. The managed resources will be taken care of when the finalizers are finished running and the objects can finally be fully collected.

The way that this is accomplished is via the `bool disposing` argument. The point of that argument is to determine whether you are cleaning up because someone called `public void Dispose()` or because you are being finalized. The most common mistake I see related to `IDisposable` is ignoring the `bool disposing` argument. That is very dangerous. Stick to the pattern!

The `using` Statement
=====================

There is only one language feature (that I'm aware of) which directly interacts with `IDisposable`: the `using` statement. It looks like this:

    :::csharp
    using (var disposable = new UnmanagedResourceHolder())
    {
        // Do something
    }

The code above is (roughly) equivalent to this code:

    :::csharp
    var disposable = new UnmanagedResourceHolder();
    try
    {
        // Do something
    }
    finally
    {
        if (disposable != null)
        {
            disposable.Dispose();
        }
    }

The advantage is that the disposable object will be disposed as soon as you are done using it (that is, as soon as your code leaves the scope of the `using` statement). This code is also exception-safe. This allows you to use unmanaged resources in a similar way as you would in a language with C++ using the [RAII](http://en.wikipedia.org/wiki/Resource_Acquisition_Is_Initialization) idiom.

For `IDisposable` objects that are short-lived you should try to always use the `using` statement.

`using` and `async`/`await`
=================================

As a bonus, this feature also works great with `async`/`await`:

    :::csharp
    private async void HandleButtonClick(object sender, EventArgs e)
    {
        using (var disposable = GetDisposable())
        {
            await DoSomeAsyncTask(disposable);
            disposable.SomeMethod();
        }
    }

The `async`/`await` language feature allows you to use the `using` statement in a lot of situations where you couldn't before because you would have to hold the `IDisposable` object while waiting for some asynchronous task to finish. Now you can write simpler code that is also exception safe.

Further Reading
===============

There are many subtleties involved in implementing finalizers and `IDisposable` correctly. To learn more you can read Microsoft's documentation on [Implementing Finalize and Dispose to Clean Up Unmanaged Resources](http://msdn.microsoft.com/en-us/library/vstudio/b1yfkh5e(v=vs.100).aspx).
