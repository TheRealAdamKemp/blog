<!-- !b
kind: post
service: blogger
title: Memory Management in Xamarin.iOS
labels: mobile, ios, xamarin
draft: True
-->

Memory management in Xamarin.iOS is a tricky subject. In order to avoid memory leaks you need to understand at least the basics of both Objective-C memory management and C# (garbage collected) memory management, and how those two worlds interact. In this post I will try to explain how all of this fits together, and I will give some specific practical advice on avoiding memory leaks in Xamarin.iOS.

<!--more-->

[TOC]

Two Worlds
=====

Xamarin.iOS programs sit between two very different worlds when it comes to memory management. On the C# side we live in a world of garbage collection, where issues like reference cycles typically don't matter. On the Objective-C side (the language of the native UIKit API) we live in a world of reference counting. There are advantages and disadvantages to both worlds, and unfortunately in some ways we have to deal with the worst of both worlds. Understanding both worlds will help you avoid common memory leaks.

C#: Garbage Collection
=====

C# memory management is accomplished with [garbage collection](http://en.wikipedia.org/wiki/Tracing_garbage_collection). In this system unused objects ("garbage") are automatically "collected". The interesting question is what counts as "unused"? An unused object is one that is no longer reachable. An object is reachable if there is a path from a "root". A root is an object that is a static field or a local variable in an active stack frame. Each object has references to other objects, which have references to other objects, and so on. The garbage collector traces from the roots through all of those references, marking all of the objects that it comes across as reachable. Once this is finished all of the objects that are not marked are considered garbage, and they are candidates for collection[^gc].

[^gc]: This is a basic description of how the garbage collection algorithm works, but there are various optimizations that can be used to speed up the implementation. For more detailed information about garbage collection and specific optimizations read Microsoft's documentation on the [Fundamentals of Garbage Collection](http://msdn.microsoft.com/en-us/library/ee787088(v=vs.110).aspx) or the excellent book [CLR via C#](http://www.amazon.com/CLR-via-Edition-Developer-Reference/dp/0735667454).

In a garbage collected environment many issues with memory leaks simply disappear. Even circular references (where two or more objects refer to each other, creating a cycle) are usually not a problem. However, despite what some people believe, it is still possible to have memory leaks in a garbage collected environment. A common scenario leading to memory leaks is when a long-living object (especially static, such as a singleton) holds a reference to other objects that don't need to be long-living. As long as that long-living object has references to the other objects those other objects will stay in memory.

Sometimes references are not obvious. C# events are a common source of memory leak issues because of their subtle introduction of references. Consider this code:

    :::csharp
    public class EventSource
    {
        public event EventHandler Event;
    }

    public class EventHandler
    {
        public EventHandler(EventSource source)
        {
            source.Event += HandleEvent;
        }

        private void HandleEvent(object sender, EventArgs e)
        {
            // Do something
        }
    }

Because of the syntax of the language it is not obvious that this code introduces a reference from `EventSource` to `EventHandler`. However, under the hood an `event` is implemented as a `multicast delegate`, which is essentially a linked list of function pointers. A delegate holds a reference to the instance object that will handle the event. That means that the line with the `+=` introduces a reference to the `EventHandler` object.

In most cases this isn't a problem, but again it can be if `EventSource` is expected to be alive longer than `EventHandler`. In order to avoid this kind of memory leak you need to remove the event handler, like this:

    :::csharp
    public class EventHandler
    {
        private readonly EventSource _source;

        public EventHandler(EventSource source)
        {
            _source = source;
            source.Event += HandleEvent;
        }

        public void RemoveHandler()
        {
            _source.Event -= HandleEvent;
        }

        private void HandleEvent(object sender, EventArgs e)
        {
            // Do something
        }
    }

The best place to do this depends on the kind of objects involved, and for Xamarin.iOS objects there are some specific good places to do this work that I will describe later.

Objective-C: Reference Counting
=====

Objective-C manages its memory using [reference counting](http://en.wikipedia.org/wiki/Reference_counting). This is similar to garbage collection (in fact some definitions of garbage collection include reference counting), but it is significantly different from the system used by C#. With reference counting each object has a field (the reference count) that tracks how many other objects are using it. Each new object starts with a reference count of 1, and each time another object wants to hold that object in memory it increments the reference count. Whenever an object no longer wants another object to stay in memory it decrements the reference count. If the reference count reaches 0 then it is immediately deallocated.

In order for reference counting to work there needs to always be a balance between the increments and decrements. That is, any time an object increments the reference count of another object it must eventually decrement it. If one object allocates another object then that counts as an implicit increment (since it starts at 1), and therefore that object must also eventually decrement the reference count. This can be tedious and error prone, and up until recently it was very easy to introduce memory leaks in Objective-C by forgetting to decrement the reference count. Also you have to be very careful to avoid reference cycles because they will lead to memory leaks. Unlike garbage collection, reference cycles in reference counted environments will always cause leaks.

In iOS 5 (and OS X 10.7) Apple introduced [Automatic Reference Counting](http://en.wikipedia.org/wiki/Automatic_Reference_Counting) or ARC. With ARC the compiler uses the knowledge it can derive from your code to automatically insert the reference count increments and decrements so that you as the programmer don't have to. It is important to note that this is still _not_ the same as C# garbage collection. This is still based on reference counting, and at runtime it works exactly the same as it did before. This is important because it means that cycles will still cause memory leaks.

Xamarin.iOS
=====

Xamarin.iOS marries these two worlds together in a way that in most cases makes iOS programming easier, but in a few cases can still lead to subtle memory leak bugs. To understand how to avoid those leaks let's explore how Xamarin.iOS deals with these two fundamentally different schemes.
