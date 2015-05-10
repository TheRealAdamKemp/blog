<!-- !b
kind: post
service: blogger
title: Taming The Android Activity, Part 2
url: http://blog.adamkemp.com/2015/05/taming-android-activity-part-2.html
labels: mobile, android, activity, xamarin, activity, async, await, async-await
blog: 6425054342484936402
draft: False
id: 1344321728560928875
-->

In [part one](http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html) of this series I covered how to use a `Fragment` to maintain state through configuration changes. In part two I will cover how to launch a new `Activity` (in-process or not) and wait for its results using C#'s `async`/`await` feature.

<!--more-->

[TOC]

Starting Activities
===================

As mentioned in part one, the `Activity` is designed to let applications reuse pieces of other applications. For instance, if you need to let the user pick a photo then you can construct an `Intent` object that describes what you want to do (pick a photo), and the OS will find an `Activity` for one of the installed applications that can satisfy that request. The other `Activity` may be in another application, but the `Intent` allows you to send it information about what you want, and then later it can send back the results (through another `Intent`).

The way the API works is you call `StartActivity` (a method in `Activity`) and give it either an `Intent` object or a `Type` (which will be used to construct an `Intent`). When you do that the OS will find the proper `Activity`, create it (possibly in another process), and then show it the user. Once that `Activity` is finished (either by the user pressing the back button or the `Activity` calling `Finish()`) then your original `Activity` will resume.

However, that's only for a simple case: launching a new `Activity` and ignoring any results. If you actually wanted to get information back from the other `Activity` then you need to instead call `StartActivityForResult`. This method is just like `StartActivity`, but it also takes an `int` that can be used to identify the request. Then you have to override the `OnActivityResult` method, which will give you back the request identifier along with a `ResultCode` and an `Intent` (for extra information). That basically looks like this:

    :::csharp
    private const int ImagePickerRequestCode = 1000;

    private void LaunchOtherActivity()
    {
        var intent = new Intent(Intent.ActionGetContent);
        intent.SetType("image/*");
        StartActivityForResult(intent, ImagePickerRequestCode);
    }

    public override void OnActivityResult(int requestCode, Result resultCode, Intent data)
    {
        if (requestCode == ImagePickerRequestCode && resultCode == Result.Ok)
        {
            // Get the image from data
        }
    }

The Problem
===========

There are several problems with this, and the root of all of them is that all results for any `Activity` you launch must go through `OnActivityResult`. This means that any time you launch an `Activity` and want results you have to put some code in that function to handle the results. This is why you need the annoying `int requestCode` argument: that is the only way to identify _which_ `Activity` you were launching so that you know what to do with the results. Now you have to be sure that each type of `Activity` that you launch in this way uses a different number, which is annoying.

Another problem is that this splits up your code. You start the `Activity` in one place, and then you handle the results elsewhere. There's no callback or anything that connects the two. You just have to know to go find that other function to see how the results are handled.

The worst problem is that this makes it very difficult to properly decouple responsibilities between views. What if you want to launch another `Activity` from a view inside a popup? You still have to handle the results in the `Activity` itself, and then you somehow have to get the results back to the view inside the popup.

This was my motivation for finding a better way. When you write a large application in Android you might have many different kinds of activities that you want to launch and then gather the results from, and forcing all of that code to go through a single function makes it very difficult to maintain.

Imagine a Better Way
====================

Before we start trying to implement anything let's first think about what we _want_ the API to look like (always a good first step to avoid [APIs like this](http://mollyrocket.com/casey/stream_0029.html)).

Obviously launching a new `Activity` and getting results is an asynchronous operation so we're going to have some kind of asynchronous API. We could do that with callbacks, which would be a huge improvement, but C# has an awesome feature that makes this even better: [`async`/`await`](https://msdn.microsoft.com/en-us/library/hh191443.aspx). Using that feature we could imagine an API that looks like this:

    :::csharp
    var intent = new Android.Content.Intent(Android.Content.Intent.ActionGetContent);
    intent.SetType("image/*");
    var result = await StartActivityForResultAsync(intent);
    if (result.ResultCode == Result.Ok)
    {
        // Get the image from data
    }

This looks awesome. There's no request code, and all of the code is in one place. Best of all, there's not even a callback. This code reads like normal synchronous code.

Gathering Requirements
======================

Now that we know what we want the API to look like let's think about what we need to accomplish it. One of the benefits of the work we did in [part one](http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html) of this series is that each `Activity` (and also each `Fragment`) in our application shares a base class. That provides us with an opportunity to put some bookkeeping in the base class that can help us achieve our goal. Based on the API we have to start with, and the API we are trying to build, we need to keep track of this information:

1. A request code for each launched `Activity`. To avoid requiring the caller to give us one we also need to somehow come up with new unique request codes automatically.
2. A `TaskCompletionSource` that can be used to provide the results asynchronously to the caller (via its `Task` property).
3. A mapping between the request codes and the `TaskCompletionSource`s.

Based on this we can start to see an implementation forming. We can use an auto-incrementing request code (starting at some arbitrary value), and we can use a `Dictionary` to map between the request codes and the `TaskCompletionSource`s.

While we're at it we will also solve another challenge that we often face when dealing with these `Activity` results: `OnActivityResult` is called _before_ `OnResume`, which in some cases may be too early to actually deal with the results. Since we're already handling sending the results back asynchronously we can fix this by also delaying the results until after `OnResume`, which is far more useful.

Implementation
==============

In the spirit of keeping as much logic in the `Fragment` instead of the `Activity` we will be putting this API in the `FragmentBase` class that we created in part one of this series. This is also important because we don't want to lose the bookkeeping information if there is a configuration change (like if the user rotates the device after you start the new `Activity` but before you get the results).

Our `FragmentActivity` class will be the same as before, but we will add some new code to the `FragmentBase` class. First, we need an interface for the results returned by our async method:

    :::csharp
    /// <summary>
    /// The information returned by an Activity started with StartActivityForResultAsync.
    /// </summary>
    public interface IAsyncActivityResult
    {
        /// <summary>
        /// The result code returned by the activity.
        /// </summary>
        Result ResultCode { get; }

        /// <summary>
        /// The data returned by the activity.
        /// </summary>
        Intent Data { get; }
    }

Now we need to add our new methods to the `FragmentBase` class. I have omitted the parts that were unchanged for brevity.

    /// <summary>
    /// The base class for top-level fragments in Android. These are the fragments which maintain the view hierarchy and state for each top-level
    /// Activity. These fragments all use RetainInstance = true to allow them to maintain state across configuration changes (i.e.,
    /// when the device rotates we reuse the fragments). Activity classes are basically just dumb containers for these fragments.
    /// </summary>
    public abstract class FragmentBase : Fragment
    {
        // This is an arbitrary number to use as an initial request code for StartActivityForResultAsync.
        // It just needs to be high enough to avoid collisions with direct calls to StartActivityForResult, which typically would be 0, 1, 2...
        private const int FirstAsyncActivityRequestCode = 1000;

        // This is static so that they are unique across all implementations of FragmentBase.
        // This is important for the fragment initializer overloads of StartActivityForResultAsync.
        private static int _nextAsyncActivityRequestCode = FirstAsyncActivityRequestCode;
        private readonly Dictionary<int, AsyncActivityResult> _pendingAsyncActivities = new Dictionary<int, AsyncActivityResult>();
        private readonly List<AsyncActivityResult> _finishedAsyncActivityResults = new List<AsyncActivityResult>();

        #region Async Activity API

        public Task<IAsyncActivityResult> StartActivityForResultAsync<TActivity>(CancellationToken cancellationToken = default(CancellationToken))
        {
            return StartActivityForResultAsyncCore(requestCode => Activity.StartActivityForResult(typeof(TActivity), requestCode), cancellationToken);
        }

        public Task<IAsyncActivityResult> StartActivityForResultAsync(Intent intent, CancellationToken cancellationToken = default(CancellationToken))
        {
            return StartActivityForResultAsyncCore(requestCode => Activity.StartActivityForResult(intent, requestCode), cancellationToken);
        }

        public override void OnActivityResult(int requestCode, Result resultCode, Intent data)
        {
            AsyncActivityResult result;
            if (_pendingAsyncActivities.TryGetValue(requestCode, out result))
            {
                result.SetResult(resultCode, data);
                _pendingAsyncActivities.Remove(requestCode);
                _finishedAsyncActivityResults.Add(result);
            }

            base.OnActivityResult(requestCode, resultCode, data);
        }

        public override void OnResume()
        {
            base.OnResume();

            FlushPendingAsyncActivityResults();
        }

        private Task<IAsyncActivityResult> StartActivityForResultAsyncCore(Action<int> startActivity, CancellationToken cancellationToken)
        {
            var asyncActivityResult = SetupAsyncActivity();
            startActivity(asyncActivityResult.RequestCode);

            if (cancellationToken.CanBeCanceled)
            {
                cancellationToken.Register(() =>
                    {
                        Activity.FinishActivity(asyncActivityResult.RequestCode);
                    });
            }

            return asyncActivityResult.Task;
        }

        private void FlushPendingAsyncActivityResults()
        {
            foreach (var result in _finishedAsyncActivityResults)
            {
                result.Complete();
            }
            _finishedAsyncActivityResults.Clear();
        }

        private AsyncActivityResult SetupAsyncActivity()
        {
            var requestCode = _nextAsyncActivityRequestCode++;
            var result = new AsyncActivityResult(requestCode);
            _pendingAsyncActivities.Add(requestCode, result);

            return result;
        }

        private class AsyncActivityResult : IAsyncActivityResult
        {
            private readonly TaskCompletionSource<IAsyncActivityResult> _taskCompletionSource = new TaskCompletionSource<IAsyncActivityResult>();

            public int RequestCode { get; private set; }

            public Result ResultCode { get; private set; }

            public Intent Data { get; private set; }

            public Task<IAsyncActivityResult> Task { get { return _taskCompletionSource.Task; } }

            public AsyncActivityResult(int requestCode)
            {
                RequestCode = requestCode;
            }

            public void SetResult(Result resultCode, Intent data)
            {
                ResultCode = resultCode;
                Data = data;
            }

            public void Complete()
            {
                _taskCompletionSource.SetResult(this);
            }
        }

        #endregion
    }

Now let's take a quick tour and see how this all works. First, there are two overloads of `StartActivityForResultAsync`. One takes a type of `Activity` as a generic argument because it's very common to want to start a new `Activity` in-process and just refer to it by its type. The other one takes an `Intent`, which is more flexible. You will typically use this variant for out-of-process activities.

These methods also take an optional `CancellationToken`, which can be used to cancel the launched `Activity`. If the token is cancelled then the code that is waiting on the async result will get a `ResultCode` that indicates that it was cancelled.

Both of those methods call into the same core routine that sets up the bookkeeping. It is responsible for creating the object that tracks the results and returning the `Task` that we can wait on.

Once the `Activity` has been started we return the `Task` object to the caller, and then we wait for a call to `OnActivityResult`. If you recall from part one of this series, that method call is actually forwarded to us by our `FragmentActivity` class (in the Android SDK there is no `OnActivityResult` method in `Fragment`, but we added one for this purpose). In `OnActivityResult` we check to see if the request code is one that is in our `Dictionary` of pending async activities. If it is then we record the `ResultCode` and the `Intent`, add it to a list of finished results, and then remove the item from our `Dictionary`. Later we will get a call to `OnResume`, which just goes through the list of finished results and calls the `Complete` method. That is the method that actually pushes the results into the `TaskCompletionSource` (by calling `SetResult`), which unblocks anything waiting on the `Task`.

And that's it. Now we have enough to start a new `Activity` and wait for its result in a single, small function. I have posted a full version of the code with a small example app on [GitHub](https://github.com/TheRealAdamKemp/AsyncStartActivityTest).

Summary
=======

So far in the first two parts of this series I have covered how to preserve state across configuration changes and how to simplify the process of starting new activities and waiting for their results. With those two challenges solved we can avoid a lot of ugly boilerplate code. However, there is still one significant source of tedious boilerplate code: communicating between these activities still has to be done through `Intent` objects. In the next part of this series I will extend this code even further to allow for directly accessing the new `Fragment` object for in-process activities.
