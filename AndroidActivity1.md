<!-- !b
kind: post
service: blogger
title: Taming The Android Activity, Part 1
url: http://blog.adamkemp.com/2015/04/taming-android-activity-part-1.html
labels: mobile, android, activity, xamarin, activity
blog: 6425054342484936402
draft: False
id: 4773351428721886886
-->

The [`Activity`](http://developer.android.com/reference/android/app/Activity.html) is a core building block in an Android application, but in some cases it can be a pain to work with. This article is part one of a series showing how to deal with some of the complexities of the `Activity` in a clean way using some of the capabilities of C# available to Xamarin.Android developers.

<!--more-->

Typically each screen in an Android application is represented by an `Activity`, and moving from one screen to another is done by starting a new `Activity`. In fact, the `Activity` and its related class `Intent` are the keys to Android's ability to let applications reuse pieces of other applications. That cross-application use case was the motivation behind the design of the `Activity`, but that design has the unfortunate side effect of making some common in-process use cases surprisingly difficult to deal with.

This series will cover three common scenarios that Android developers face in which the design of the `Activity` class causes problems:

1. Dealing with device rotation (and other configuration changes)
2. Launching and waiting for the results of another `Activity`
3. Communicating between (in-process) `Activity`s

Each of these is very common and yet is surprisingly difficult to do on Android, especially compared to the way that view controllers work in iOS.

[TOC]

Configuration Changes
=====================

The [Android documentation](http://developer.android.com/reference/android/app/Activity.html#ConfigurationChanges) has this to say about configuration changes (emphasis added):

> If the configuration of the device (as defined by the Resources.Configuration class) changes, then anything displaying a user interface will need to update to match that configuration. Because Activity is the primary mechanism for interacting with the user, it includes special support for handling configuration changes.
>
> **Unless you specify otherwise, a configuration change** (such as a change in screen orientation, language, input devices, etc) **will cause your current activity to be destroyed**, going through the normal activity lifecycle process of onPause(), onStop(), and onDestroy() as appropriate.

What this means is that any "configuration change" will cause your `Activity` object to be destroyed and then recreated. What's a "configuration change"? There are actually a lot of things that count (see the [complete list](http://developer.android.com/reference/android/content/res/Configuration.html)), but one of the most common is an orientation change. As a result, if a user rotates his device from portrait to landscape (or vice versa) then your `Activity` will be destroyed and recreated.

The most obvious consequence of having your `Activity` get destroyed is that all of the views also have to be recreated, but the most serious consequence is that all state stored in the `Activity` (meaning your fields and properties) will be lost, and a brand new instance of your `Activity` class will be created _from scratch_ instead.

Handling Configuration Changes
==============================

There are a few approaches to dealing with this problem:

1. Disable the behavior
2. Serialize and deserialize your state
3. Use a retained `Fragment`

The first option is to disable this behavior, which can be done by setting the [`configChanges`](http://developer.android.com/reference/android/R.attr.html#configChanges) property of the `Activity` to the configuration changes that you _don't_ want to cause the `Activity` to be destroyed. This seems like a great option, and you will find many people recommending it. However, [Google discourages this approach](http://developer.android.com/guide/topics/resources/runtime-changes.html#HandlingTheChange):

> This technique should be considered a last resort when you must avoid restarts due to a configuration change and is not recommended for most applications.

The second option was the best approach for a while, and many apps no doubt still use this approach. When an `Activity` is being destroyed for a configuration change it will receive a call to [`OnSaveInstanceState`](http://developer.android.com/reference/android/app/Activity.html#onSaveInstanceState(android.os.Bundle)). This method has `Bundle` argument that can be used to stash data using a key/value system. Basic types are supported by default, but more complex data types are difficult to deal with. Once the new `Activity` is created it will receive a call to [`OnRestoreInstanceState`](http://developer.android.com/reference/android/app/Activity.html#onRestoreInstanceState(android.os.Bundle,%20android.os.PersistableBundle)), which is handed the same `Bundle` object in order to fetch the stashed data.

The downside of this approach is that it is tedious and error prone. If you forget any fields then your application will have subtle bugs any time a user rotates his device. Ideally we could just throw a whole object from the old `Activity` to the new one. In fact, there _is_ a deprecated API for doing just this (see [`OnRetainNonConfigurationInstance`](http://developer.android.com/reference/android/app/Activity.html#onRetainNonConfigurationInstance()) and [`GetLastNonConfigurationInstance`](http://developer.android.com/reference/android/app/Activity.html#getLastNonConfigurationInstance())), but that mechanism has been replaced by a better one.

Since Android 3.0 the current recommended solution to dealing with configuration changes is with a retained `Fragment`.

Fragments
=========

A [`Fragment`](http://developer.android.com/reference/android/app/Fragment.html) is kind of like a miniature `Activity`. It has a lifecycle, state, and optionally a view hierarchy. A `Fragment` is attached to an `Activity` via the `Activity`'s `FragmentManager`.

By default whenever an `Activity` is destroyed for a configuration change its associated `Fragment`s are also destroyed. However, you can request that a `Fragment` be retained by setting the `RetainInstance` property to `true`, which allows the entire object and all of its fields (but not its views) to be reused.

Therefore, the best technique for dealing with configuration changes is to actually move most of your `Activity`'s code into a `Fragment` instead. The `Activity` is then merely a dumb shell used to create the `Fragment` and deal with `Activity`-specific issues like `Intent`s. Here is an overview of how this technique works:

1. When the `Activity` is created it uses its `FragmentManager` to search for an existing instance of its `Fragment` (identified by a tag string).
2. If an existing `Fragment` was not found then a new one is created and added to the `Activity`.

Other than dealing with things like `Intent`s and results from other `Activity`s (both to be covered in future segments of this series) the `Activity` class doesn't have much else to do. As you can imagine, the code to perform these steps will end up looking fairly boilerplate. In fact, this is a great opportunity for some code reuse.

Example
=======

As an example of how to deal with this problem in a generic way let's start with the Xamarin.Android stock template that you get when you create a new application. If you run this template without any modifications then you get a simple application with a button on it. When you click the button it shows you how many times it has been clicked. In order to demonstrate the problem click the button a few times and then rotate the device. The first thing you'll notice is that the button text reverts to the original "Hello World" text. If you click the button again you'll also notice that the count starts over. This is the bug we will be fixing.

In order to fix this we will introduce two new base classes: `FragmentActivity` and `FragmentBase`. These classes can be dropped in to any application, and we will build on them further throughout this series to add other useful capabilities. For this problem, though, the classes are pretty simple. Here is the code:

    :::csharp
    /// <summary>
    /// An Activity that uses a retained Fragment for its implementation.
    /// </summary>
    public abstract class FragmentActivity<TFragment> : Activity where TFragment : FragmentBase, new()
    {
        /// <summary>
        /// The top-level fragment which manages the view and state for this activity.
        /// </summary>
        public FragmentBase Fragment { get; protected set; }

        /// <summary>
        /// The tag string to use when finding or creating this activity's fragment. This will be contructed using the type of this generic instance.
        /// </summary>
        protected string FragmentTag
        {
            get
            {
                return GetType().Name;
            }
        }

        /// <inheritdoc />
        protected override void OnCreate(Bundle savedInstanceState)
        {
            base.OnCreate(savedInstanceState);

            LoadFragment();
        }

        /// <inheritdoc />
        public override void OnAttachedToWindow()
        {
            base.OnAttachedToWindow();
            Fragment.OnAttachedToWindow();
        }

        /// <inheritdoc />
        protected override void OnNewIntent(Intent intent)
        {
            Fragment.OnNewIntent(intent);
        }

        /// <summary>
        /// Loads the fragment for this activity and stores it in the Fragment property.
        /// </summary>
        protected virtual void LoadFragment()
        {
            Fragment = FragmentBase.FindOrCreateFragment<TFragment>(this, FragmentTag, global::Android.Resource.Id.Content);
        }

        /// <inheritdoc />
        protected override void OnActivityResult(int requestCode, Result resultCode, Intent data)
        {
            Fragment.OnActivityResult(requestCode, resultCode, data);
        }
    }

    /// <summary>
    /// The base class for top-level fragments in Android. These are the fragments which maintain the view hierarchy and state for each top-level
    /// Activity. These fragments all use RetainInstance = true to allow them to maintain state across configuration changes (i.e.,
    /// when the device rotates we reuse the fragments). Activity classes are basically just dumb containers for these fragments.
    /// </summary>
    public abstract class FragmentBase : Fragment
    {
        /// <summary>
        /// Tries to locate an already created fragment with the given tag. If the fragment is not found then a new one will be created and inserted into
        /// the given activity using the given containerId as the parent view.
        /// </summary>
        /// <typeparam name="TFragment">The type of fragment to create.</typeparam>
        /// <param name="activity">The activity to search for or create the view in.</param>
        /// <param name="fragmentTag">The tag which uniquely identifies the fragment.</param>
        /// <param name="containerId">The resource ID of the parent view to use for a newly created fragment.</param>
        /// <returns></returns>
        public static TFragment FindOrCreateFragment<TFragment>(Activity activity, string fragmentTag, int containerId) where TFragment : FragmentBase, new()
        {
            var fragment = activity.FragmentManager.FindFragmentByTag(fragmentTag) as TFragment;
            if (fragment == null)
            {
                fragment = new TFragment();
                activity.FragmentManager.BeginTransaction().Add(containerId, fragment, fragmentTag).Commit();
            }

            return fragment;
        }

        /// <inheritdoc />
        public override void OnCreate(Bundle savedInstanceState)
        {
            base.OnCreate(savedInstanceState);

            RetainInstance = true;
        }

        /// <summary>
        /// Called when this fragment's activity is given a new Intent.
        /// </summary>
        /// <remarks>The default implementation does nothing</remarks>
        public virtual void OnNewIntent(Intent intent)
        {
        }

        /// <summary>
        /// Called when this fragment's activity is attached to a window.
        /// </summary>
        /// <remarks>The default implementation does nothing</remarks>
        public virtual void OnAttachedToWindow()
        {
        }
    }

As you can see, `FragmentActivity` is a generic abstract class with a type parameter to specify the type of the `Fragment` that it should use. This class creates and holds on to the `Fragment` and forwards a few useful messages to the `Fragment` that otherwise would be handled by the `Activity`. The `FragmentBase` class is an abstract class that is used as the base class for any `Fragment`s used by a `FragmentActivity`. Its static `FindOrCreateFragment` method, as its name implies, is used to find an existing instance of a `Fragment` or create a new one if one is not found. Also note that `RetainInstance` is set to `true` when this `Fragment` is created, which is the key to allowing the instance to be reused. The other methods are just there to receive notifications from the `Activity`.

The way you use these classes is simple. For each `Activity` you will create a pair of classes: a `Fragment` that inherits from `FragmentBase` and an `Activity` that inherits from `FragmentActivity`. The generic type argument links them together. In many cases the `Activity` doesn't need _any_ additional code (it will just be an empty class), and all of the important code goes in the `Fragment`. To see this in action this is how I adapted the Xamarin.Android template to use these new classes ([complete code](https://github.com/TheRealAdamKemp/FragmentActivityTest)):

    :::csharp
    [Activity(Label = "FragmentActivityTest", MainLauncher = true, Icon = "@drawable/icon")]
    public class MainActivity : FragmentActivity<MainActivityFragment>
    {
    }

    public class MainActivityFragment : FragmentBase
    {
        private int _count = 0;
        private Button _button;

        public override View OnCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState)
        {
            var view = inflater.Inflate(Resource.Layout.Main, container, attachToRoot: false);

            _button = view.FindViewById<Button>(Resource.Id.myButton);

            if (_count != 0)
            {
                UpdateButtonText();
            }

            _button.Click += delegate
                {
                    _count++;
                    UpdateButtonText();
                };

            return view;
        }

        private void UpdateButtonText()
        {
            _button.Text = string.Format("{0} clicks!", _count);
        }
    }

The first thing you'll notice is that, as I mentioned before, the `Activity` has no code in it. Looking at the `Fragment` you'll notice that it looks very similar to the original code, but with a few key tweaks. Let's look at what I had to change.

The first change was the loading of the layout file. The original code looked like this:

    :::csharp
    SetContentView(Resource.Layout.Main);

`SetContentView` is a method of `Activity`, but we're not in an `Activity` anymore. Instead, we just have to load the layout and return it. For this purpose we are given a `LayoutInflater`, and we use it like this:

    :::csharp
    var view = inflater.Inflate(Resource.Layout.Main, container, attachToRoot: false);

There are two additional arguments being used here, and both are important. The first is the container `ViewGroup` that is passed to us as an argument to `OnCreateView`. This is the container in which the view we return will be inserted. The second is a boolean that tells the `LayoutInflater` that we don't want it to insert the inflated view into that container.[^inflate]

[^inflate]: This may seem strange. Why are we passing in the container if we aren't inserting the view into it? It turns out that there is a good reason for this, which is explained in detail by [this article](http://possiblemobile.com/2013/05/layout-inflation-as-intended/). If you leave off the last argument the default is `true`, and you will get an exception because the view is inserted twice. If you pass `null` as the second argument then you won't crash, but your top-level `LayoutParams` in your layout file will be ignored. Thus we pass in the container _and_ we tell it not to attach.

Moving on, we have an extra bit of initialization code:

    :::csharp
    if (_count != 0)
    {
        UpdateButtonText();
    }

This code is necessary because while the `Fragment` is reused across configuration changes _the view is not_. That means this method will be called multiple times on the same `Fragment` instance[^OnDestroyView], and it is up to us to initialize the view with the current state[^viewState]. In order to handle this I created a field for the button and refactored the code for updating the text into a method that I can call in multiple places. Since the initial text comes from the layout file and doesn't match the format used after clicking the button I check first to see if the button has ever been pressed.

[^OnDestroyView]: There is a corresponding method `OnDestroyView`, which can be used to do any necessary cleanup when the old view is destroyed during a configuration change (or when the `Fragment` itself is going to be destroyed).

[^viewState]: Some views do their own saving and restoring of temporary state during configuration changes. For instance, an `EditText` will save the text that has been entered, the cursor location, and the current selection. This is handled by `OnSaveInstanceState` and `OnRestoreInstanceState` in the [`View` class](http://developer.android.com/reference/android/view/View.html).

Lastly, I return the view that was created since that is needed by the `Activity` in order to insert it into the view hierarchy.

Summary
=======

As you can see, this approach makes it very easy to handle configuration changes by mostly just ignoring them. The only remaining wrinkle is that the views are still destroyed and recreated, which requires a bit of extra initialization. This is necessary because the views may actually adapt to the configuration change. The good news is that we no longer have to tediously save and restore every state field.

I use this technique in every Android application I write, and it works very well. I hope that this post and the example code will help you save time dealing with the same issue.

In the next part of this series I will explain how to deal with the problem of starting a new `Activity` and waiting for its results.
