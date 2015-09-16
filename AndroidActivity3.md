<!-- !b
kind: post
service: blogger
title: Taming the Android Activity, Part 3
url: http://blog.adamkemp.com/2015/09/taming-android-activity-part-3.html
labels: mobile, android, activity, xamarin, fragment, event, intent
blog: 6425054342484936402
draft: False
id: 7316046307153947301
-->

In the parts [one](http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html) and [two](http://blog.adamkemp.com/2015/05/taming-android-activity-part-2.html) of this series I covered how to use a `Fragment` to maintain state through configuration changes and how to launch a new `Activity` and wait for its results using `async`/`await`. In the third part I take this a step further and show how to get direct access to a new (in-process) `Activity` instance so that you can call methods on it, use events, or whatever else you need to do.

<!--more-->

[TOC]

Activities - Taking Decoupling Too Far?
=======================================

The Android `Activity` is designed to be a modular piece of UI that can be reused across applications. For this reason Android's design forces complete decoupling. When you launch a new `Activity` you cannot access the new instance directly. Instead, you have to communicate with it through `Intent` objects. You use an `Intent` when launching the `Activity` in order to give it input, and when the `Activity` finishes it can communicate back its results via another `Intent` object. In this way the `Activity` is sure to work no matter how it was launched, whether by another in-process `Activity` or some other application's `Activity`.

This approach is great for allowing apps to interoperate, but in my opinion it ignores one important reality: by far, most `Activity` instances are launched in-process, and many are only useful within that process. Unfortunately, the Android architecture is designed exclusively for the inter-process use case, which makes the more common in-process use case unnecessarily tedious.

The biggest downside to the design is that it makes launching and gathering results from new UI screens very difficult. In most UI frameworks when a developer needs to show a new UI he simply needs to construct a new object by calling its constructor and passing in any necessary data as arguments. Further, he can call methods, set properties, and attach to events in order to communicate with the new object. In contrast, on Android he would have to deal with `Intents`, possible serializing any complex data structures or even implementing a [Content Provider](http://developer.android.com/guide/topics/providers/content-providers.html). In order to get results back he would likewise need to deserialize data or pull data from a Content Provider.

Generally I encourage strategies to [decouple code](http://blog.adamkemp.com/2015/03/decoupling-views.html), but I think Android has taken this too far by forcing decoupling across processes. In this post I will show a better way.

One Neat Trick
==============

The only methods Android provides for launching an `Activity` are the `StartActivity`/`StartActivityForResult` methods. Neither of these methods provide access to the actual `Activity` instance that Android automatically creates for you. Somehow we need to be able to get access to that object so that we can interact with it. Fortunately, there is an API that we can use for this: the `Application.IActivityLifecycleCallbacks` interface. This is an interface that you can implement to handle the various `Activity` lifecycle events for all `Activity` instances that exist in the current process. In order to use this interface you can call `RegisterActivityLifecycleCallbacks` on the `Application` instance. Once you've done that you can handle all of the `Activity` lifecycle events (`OnCreate`, `OnDestroy`, `OnPause`, etc.) for all `Activity` objects in the entire application. The specific event we care about is `OnCreate`, which is called each time an `Activity` instance is created. Since each of these callbacks is also passed the `Activity` instance itself we can use this callback to get the instance that Android created for us.

Designing the API
=================

Now that we have a technique for getting access to any `Activity` that is created in our application we can start to piece together how we can extend our existing `FragmentActivity` and `FragmentBase` classes (see [part 2](http://blog.adamkemp.com/2015/05/taming-android-activity-part-2.html)) to give clients access to that instance as well. First, we need to think about the API that we want to build. While the callbacks previously mentioned give us access to an `Activity` instance, what we actually need is access to an associated `Fragment`. The reason is that, as described in [part one](http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html), the `Activity` object might be destroyed and recreated multiple times, which makes it not very useful. What we really want is the retained `Fragment` for that `Activity`, which holds all of the state.

Further, since the creation of the `Activity` and the `Fragment` both are asynchronous operations we need a way to pass the `Fragment` instance back to the caller at some point in the future. We could use a `Task` for this, which would be nice, but since I am already using a `Task` to get back the results of the `Activity` I chose to use a callback in this case. You could easily change this in your implementation.

Combining these two requirements I came up with this API:

    :::csharp
    public Task<IAsyncActivityResult> StartActivityForResultAsync<TFragmentActivity, TFragment>(Action<TFragment> fragmentInitializer, CancellationToken cancellationToken = default(CancellationToken))
        where TFragmentActivity : IFragmentActivity
        where TFragment : Fragment
    {
        // ...
    }

The usage then would look like this:

    :::chsarp
    StartActivityForResultAsync<MyActivity, MyActivityFragment>(fragment =>
        {
            // Use fragment for setting properties, calling methods, or attaching to events.
        });

I will refer to the `Action<TFragment>` callback that you pass in as a "`Fragment` initializer callback" to distinguish it from the `Activity` lifecycle event callbacks.

Implementation
==============

To make this work we're going to start with the code from [part two](http://blog.adamkemp.com/2015/05/taming-android-activity-part-2.html) and extend it a bit. First, we need to tweak the `FragmentActivity` class to add an event that will tell us when its `Fragment` is created. In order to make some generic code a bit easier to deal with we'll also add a simple interface:

    :::csharp
    /// <summary>
    /// An interface for an Activity that uses a retained Fragment for its implementation.
    /// </summary>
    public interface IFragmentActivity
    {
        /// <summary>
        /// The top-level fragment which manages the view and state for this activity.
        /// </summary>
        Fragment Fragment { get; }

        /// <summary>
        /// Invoked when the main fragment is first created.
        /// </summary>
        event EventHandler FragmentLoaded;
    }

Implementing this interface in `FragmentActivity` is straightforward so I'll skip forward to the `FragmentBase` class.

The first thing we need is the ability to register for lifecycle callbacks. In order to avoid holding this object in memory for too long we also need to keep track of when we can safely unregister for the callbacks. To accomplish this we will add a field to our class to track how many `Fragment` initialization callbacks (the callbacks passed in to our new `StartActivityForResultAsync` overload) we have pending. When this count is incremented from 0 to 1 we will register from the callbacks, and when it is decremented to 0 we will unregister. Then we just need to increment it whenever someone calls our new `StartActivityForResultAsync` overload and decrement it whenever we satisfy one of those callbacks. The support code look like this:

    :::csharp
    private int _numberOfPendingFragmentInitializers;

    private void AddPendingFragmentInitializer()
    {
        _numberOfPendingFragmentInitializers++;
        if (_numberOfPendingFragmentInitializers == 1)
        {
            var application = (Application)Application.Context;
            application.RegisterActivityLifecycleCallbacks(this);
        }
    }

    private void RemovePendingFragmentInitializer()
    {
        if (_numberOfPendingFragmentInitializers <= 0)
        {
            throw new InvalidOperationException("Too many calls to RemovePendingFragmentInitializer");
        }

        _numberOfPendingFragmentInitializers--;
        if (_numberOfPendingFragmentInitializers == 0)
        {
            var application = (Application)Application.Context;
            application.UnregisterActivityLifecycleCallbacks(this);
        }
    }

Just in case we should also be sure to unregister in `OnDestroy`:

    :::csharp
    public override void OnDestroy()
    {
        base.OnDestroy();

        if (_numberOfPendingFragmentInitializers != 0)
        {
            var application = (Application)Application.Context;
            application.UnregisterActivityLifecycleCallbacks(this);
            _numberOfPendingFragmentInitializers = 0;
        }
    }

We'll come back to these functions later. The next step is to keep track of the `Fragment` initializer callbacks themselves so that we can find them and call them when needed. We already have a private class (`AsyncActivityResult`) for keeping track of our pending async `Activity` requests so we can just add the initializer callback there:

    :::csharp
    public Action<Fragment> FragmentInitializer { get; private set; }

    public AsyncActivityResult(int requestCode, Action<Fragment> fragmentInitializer)
    {
        RequestCode = requestCode;
        FragmentInitializer = fragmentInitializer;
    }

Now we have to have some code that calls this initializer. This part is tricky for a few reasons. First, the lifecycle callbacks that we will be receiving are for `Activity` objects, not `Fragment` objects. What we want is the `Fragment`. When an `Activity` is first created (even one of our `FragmentActivity` subclasses) it doesn't have a `Fragment`. There's a delay between when the `Activity` is created and when it creates its `Fragment`. That is why we added the `FragmentLoaded` event to `FragmentActivity`. The second complication is that, as mentioned in [part one](http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html), an `Activity` may be destroyed and recreated at pretty much any time. That means even if we find an `Activity` we're interested in and attach to its `FragmentLoaded` event we still have to be prepared for that `Activity` to be destroyed before it actually loads its `Fragment`. In that case a new `Activity` will be created, and we have to attach to _its_ `FragmentLoaded` event. We can't stop looking until we finally get that event handler callback.

In order to identify the `Activity` instances we are interested in when we get our lifecycle callbacks we will add some extra data to the `Intent` object we use to launch it. This extra data will be an integer recording the request code that we used. It's important to note here that the request codes are unique across instances of `FragmentBase` so we won't mix them up. We did this by making the `_nextAsyncActivityRequestCode` field `static`. We will add this extra data at the point where we are creating our `Intent` object, which happens in our `StartActivityForResultAsync` method:

    :::csharp
    public Task<IAsyncActivityResult> StartActivityForResultAsync<TFragmentActivity, TFragment>(Action<TFragment> fragmentInitializer, CancellationToken cancellationToken = default(CancellationToken))
        where TFragmentActivity : IFragmentActivity
        where TFragment : Fragment
    {
        Action<Fragment> fragmentInitializerAdaptor = null;
        if (fragmentInitializer != null)
        {
            fragmentInitializerAdaptor = fragment => fragmentInitializer((TFragment)fragment);
        }

        return StartActivityForResultAsyncCore(
            requestCode =>
            {
                AddPendingFragmentInitializer();
                var intent = new Intent(Activity, typeof(TFragmentActivity));
                intent.PutExtra(AsyncActivityRequestCodeExtra, requestCode);
                Activity.StartActivityForResult(intent, requestCode);
            },
            cancellationToken,
            fragmentInitializerAdaptor);
    }

The `StartActivityForResultAsyncCore` method does some setup of the `AsyncActivityResult` object, but it uses a callback to do the work of creating the `Intent` and launching it. In this case we need to add our extra data and also call `AddPendingFragmentInitializer` so that we can register for our lifecycle event callbacks.

You may have also noticed the `fragmentInitializerAdaptor` variable. This code is just to avoid using generics for the `AsyncActivityResult` class, which keeps track of the `Fragment` initializer callback for us. The code that will call this callback doesn't know the type of the `Fragment`, and it would be difficult to keep track of that information so we encode it in a wrapper lambda via a downcast.

Now we have recorded the `Fragment` initializer callback and registered for our lifecycle event callbacks so the next step is implementing those lifecycle event callbacks. The only callback we care about is `OnCreate`. The rest are just empty methods. Here is the interesting one:

    :::csharp
    void Application.IActivityLifecycleCallbacks.OnActivityCreated(Activity activity, Bundle savedInstanceState)
    {
        var fragmentActivity = activity as IFragmentActivity;
        if (fragmentActivity == null)
        {
            return;
        }

        var intent = activity.Intent;
        if (intent != null && intent.HasExtra(AsyncActivityRequestCodeExtra))
        {
            int requestCode = intent.GetIntExtra(AsyncActivityRequestCodeExtra, 0);
            AsyncActivityResult asyncActivityResult;
            if (_pendingAsyncActivities.TryGetValue(requestCode, out asyncActivityResult))
            {
                if (asyncActivityResult.FragmentInitializer == null)
                {
                    return;
                }

                fragmentActivity.FragmentLoaded += (s, e) =>
                {
                    asyncActivityResult.FragmentInitializer(fragmentActivity.Fragment);

                    // It is possible that this activity is created and destroyed multiple times before loading the fragment.
                    // Don't stop listening for new activities until we actually get the fragment we are interested in.
                    RemovePendingFragmentInitializer();
                };
            }
        }
    }

Remember that this method will be called for _every_ `Activity` instance created in our application while we are still registered so most of the code is there to filter out instances we don't care about. First we ignore any `Activity` that doesn't implement our new interface `IFragmentActivity`. Next we filter out any instances that don't have our expected extra data in the `Intent`. After that we have to check if the request code stored in that extra data is one of the request codes that we know about. Lastly, we ignore any instances that don't have a `Fragment` initializer.

Once we know that the `Activity` instance that was just created is one that we care about we need to attach to its `FragmentLoaded` event. When that event is called we can then call the `Fragment` initializer (giving it the `Fragment` instance). Again, there's a chance that this event will never be triggered because this particular `Activity` instance may get destroyed before the `Fragment` is loaded. That's why it's important to only call `RemovePendingFragmentInitializer` inside the event handler so that we keep looking for new `Activity` instances as long as necessary.

Example
=======

The implementation is now complete. Now let's look at an example usage. For that I will just take the example from [part 2](http://blog.adamkemp.com/2015/05/taming-android-activity-part-2.html) and modify it to use the new API. There is only one small function that we need to modify so I'll just show you a before and after. This is the original code:

    :::csharp
    _button.Click += async (s, e) =>
    {
        var result = await StartActivityForResultAsync<AsyncActivity>();
        if (result.ResultCode == Result.Ok)
        {
            _text = result.Data.GetStringExtra(AsyncActivity.TextExtra);
            UpdateText();
        }
    };

Note that we have to check the result code and then use the `Intent` to pull out the data we care about. This is a simple example, but you can imagine that this could get quite complex if the result data were complex. What we want instead is to use a regular C# event. First we need to add that event to our `AsyncActivityFragment` class so here is that code:

    :::csharp
    public event EventHandler DoneClicked;

    private void OnDoneClicked()
    {
        if (DoneClicked != null)
        {
            DoneClicked(this, EventArgs.Empty);
        }
    }

Then we add the invocation:

    :::csharp
    button.Click += delegate
    {
        OnDoneClicked();
        var resultData = new Intent();
        resultData.PutExtra(AsyncActivity.TextExtra, _editText.Text);
        Activity.SetResult(Result.Ok, resultData);
        Activity.Finish();
    };

Note that I left the rest of the `Intent`-based code in case this `Activity` is used outside of our application. If that's not the case then you could remove that code.

Now that we have our event we just need to use it, which requires using our new overload of `StartActivityForResultAsync`. Here it is:

    :::csharp
    _button.Click += (s, e) => StartActivityForResultAsync<AsyncActivity, AsyncActivityFragment>(fragment =>
    {
        fragment.DoneClicked += delegate
        {
            _text = fragment.Text;
            UpdateText();
        };
    });

Now we pass in a callback (our "`Fragment` initializer callback), and in that callback we have access to the `Fragment`. Then we can just attach to the new event that we added to the `Fragment`. From that event we can directly access the `Text` property. Now we have no need of the `Intent`. This code is simpler, easier to understand, easier to maintain, and entirely type-safe.

The full example with all of the code for `FragmentActivity`, `FragmentBase`, and our example usage is available on [GitHub](https://github.com/TheRealAdamKemp/ActivityInstanceAccess).

Summary
=======

Through all three parts of this series you have learned how to deal with preserving state across configuration changes, how to use `async`/`await` to wait for `Activity` results, and now how to get direct access to the `Fragment` object for a new `Activity`. Using these techniques you can greatly reduce the complexity of dealing with multi-screen Android applications. Stay tuned for one more addendum post in which I will explain the one (rare) scenario that the previous two posts don't handle well.
