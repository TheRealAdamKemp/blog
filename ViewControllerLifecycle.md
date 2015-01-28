<!-- !b
kind: post
service: blogger
title: View Controller Lifecycle
url: http://blog.adamkemp.com/2015/01/view-controller-lifecycle.html
labels: mobile, ios, xamarin, view controller, UIViewController, lifecyle
blog: 6425054342484936402
draft: False
id: 7358270101973893728
-->

New iOS developers are often confused about the life cycle of view controllers. In this post I will walk through the various life cycle methods and explain how to use them and some common mistakes to avoid.

<!--more-->

[TOC]

Life Cycle Overview
===================

View controllers have a slightly more complex life cycle than views, and it may not be clear what should be done at each state of that life cycle. Here are some of the stages:

* Construction
* `LoadView`
* `ViewDidLoad`
* `ViewWillAppear`
* `ViewDidAppear`
* `ViewWillDisappear`
* `ViewDidDisappear`
* `ViewWillLayoutSubviews`
* `ViewDidLayoutSubviews`
* `UpdateViewConstraints`
* `WillMoveToParentViewController`
* `DidMoveToParentViewController`

The most important thing to note is that the `View` of a view controller is not created until it is needed. This can make some parts of a view controller's code a bit more complex (more on that later), but it allows for view controllers to be more lightweight until they are actually put on screen. [^viewDidUnload]

[^viewDidUnload]: Up until iOS 6 a view controller could also _unload_ a view after it had been loaded, which made the life cycle even more complex. Apple found that unloading a view had little benefit, and was the source of many bugs due to the complexity of handling it properly. Therefore they deprecated the view unloading life cycle methods and stopped calling them. You should never implement `ViewWillUnload` or `ViewDidUnload`. In fact, Apple's recommendation was to remove those methods even from apps that supported older versions of iOS.

View Loading
============

`LoadView` is called when the view controller needs to create its top-level view. Specifically, this method is called when the `View` property getter is accessed for the first time. The sole responsibility of `LoadView` is to create a view and assign it to the `View` property. In most cases there is no need to override this method. The default implementation looks for a .xib using the name supplied in the base `UIViewController` constructor or the name of the class. If there is no .xib then it constructs a new `UIView`. If you need to implement this method yourself (perhaps to use a custom view type as the top-level view) then you would do it like this:

    :::csharp
    public override void LoadView()
    {
        View = new MyCustomView();
    }

You may optionally assign a _temporary_ size to the view (perhaps based on the screen size), but remember that the size of the view controller's view is ultimately assigned by whatever puts it on screen (see my previous blog post on [layout gotchas](http://blog.adamkemp.com/2014/11/ios-layout-gotchas-and-view-controller.html)). You should generally avoid doing too much work in this method aside from creating that top-level view. If you have other properties to set or other views to create then you should defer those until `ViewDidLoad` so that if in the future you decide to replace `LoadView` with a .xib instead then you can just delete the `LoadView` method and leave the rest of the code alone.

`ViewDidLoad` is called after `LoadView` finishes, and that method is used to finish initializing the view. You can use this method to set additional properties of the `View`; create, initialize, and add more subviews; and add gesture recognizers. Remember that the view does not yet have a final size at this point so you should _not_ be doing layout in this method (again, refer to my previous blog post on [layout gotchas](http://blog.adamkemp.com/2014/11/ios-layout-gotchas-and-view-controller.html)).

It is important to note that `LoadView` and `ViewDidLoad` can be called at any time between constructing the view controller and putting it on screen, and you should not make any assumptions about external state in these functions. One example of an assumption that is easy to make but dangerous is using the `NavigationController` property. This property walks the view controller hierarchy looking for a `UINavigationController`, which it will only find if the view controller is pushed into a navigation controller. It is possible that a view controller's view is loaded in response to being pushed into a navigation controller, in which case this property will be non-`null` and usable. However, it is also possible that something else could trigger loading the view _before_ it is pushed into a view controller, and in that case the `NavigationController` property will be `null`. It is best to defer any uses of this property until `ViewWillAppear`.

View Appearance and Disappearance
=================================

Speaking of, the next few life cycle methods relate to appearance and disappearance. When a view controller's `View` is about to be shown its `ViewWillAppear` method is called. Specifically, this method is called when the view controller's `View` is _about_ to be added to a window. Within this method the view is not _yet_ in a window (`View.Window` will be `null`), and therefore it is not yet visible to a user. You can use this method to update any views before they are shown to the user.

After the view has been added to the window the `ViewDidAppear` method is called. In this method `View.Window` will _not_ be `null`, and therefore the view will actually be visible to the user. You should avoid making visible changes to views at this point since the user will have already seen the previous state of the view. However, you can use this method to initiate animations or loading actions that shouldn't happen until the user can actually see the view.

Likewise, `ViewWillDisappear` is called when a view controller's view is about to leave the window, and `ViewDidDisappear` is called after it has been removed from the window.

View Layout
===========

For layout purposes there are three methods to override. `ViewWillLayoutSubviews` and `ViewDidLayoutSubviews` are called before and after the view does its layout, respectively. In between these two methods the auto-layout and/or auto-resizing mechanisms take effect and the view's `LayoutSubviews` method is called. For doing manual layout the best method to override is `ViewDidLayoutSubviews` since it happens after any auto-layout or auto-resizing calculations have been applied. If you are using auto-layout then you can use `UpdateViewConstraints` to modify or replace the constraints before they are applied.

View Controller Hierarchy Changes
=================================

Lastly, there are two methods related to notifications about changes to the view controller hierarchy, which is used for [container view controllers](https://developer.apple.com/library/ios/featuredarticles/ViewControllerPGforiPhoneOS/CreatingCustomContainerViewControllers/CreatingCustomContainerViewControllers.html#//apple_ref/doc/uid/TP40007457-CH18-SW6) like `UINavigationController`. `WillMoveToParentViewController` is called when a view controller is about to move to a new parent view controller. The current parent view controller is still accessible in the `ParentViewController` property, and the new parent is passed in as an argument (`null` means it is being removed from its parent). `DidMoveToParentViewController` is called after the `ParentViewController` property has been updated. There are very few uses for these functions, and in most cases I have found that other life cycle methods are more suitable.

Properly Handling Delayed View Loading
======================================

When a view controller is first constructed it doesn't have a view. That means you should not try to access the `View` property from within the constructor[^viewInConstructor]. It also means that you should write your public API carefully

[^viewInConstructor]: Technically you can access the `View` property in a constructor, but doing so will trigger calls to `LoadView` and `ViewDidLoad`, which may assume that the code in the constructor has already run. This is very likely to cause problems and so it is a good idea to avoid it.

For instance, consider a view controller that has a public property for setting the text of a label. You may be tempted to write it like this:

    :::csharp
    private UILabel _label; // Created in ViewDidLoad

    public string LabelText
    {
        get
        {
            return _label.Text;
        }

        set
        {
            // WRONG!
            _label.Text = value;
        }
    }

The problem here is that this public property may be used before the view is actually loaded, which means the label might not yet exist. You would crash in that case. The proper way to handle this is to have a separate field to store the property value and synchronize that with the view when it is created. However, you also have to make sure you push the value into the view whenever the property is set _after_ the view is loaded. Here is the proper pattern for handling this:

    :::csharp
    private UILabel _label;
    private string _labelText = DefaultLabelText;

    private void UpdateLabelText()
    {
        _label.Text = _labelText;
    }

    public override void ViewDidLoad()
    {
        _label = new UILabel();
        UpdateLabelText();
    }

    public string LabelText
    {
        get { return _labelText; }

        set
        {
            if (_labelText != value)
            {
                _labelText = value;

                if (IsViewLoaded)
                {
                    UpdateLabelText();
                }
            }
        }
    }

Note carefully how the setter is implemented: the new value is stored in a field, and then we check `IsViewLoaded` to determine whether to push the new value into the view. If the view doesn't exist we just wait until it is created and push the value then. The `IsViewLoaded` property is important to remember. This alternative approach is both obvious and wrong:

    :::chsarp
    // WRONG!
    if (View != null)
    {
        UpdateLabelText();
    }

Recall that the view is loaded the first time that the `View` property is accessed. That means the code above actually _causes_ the view to load, and therefore would always execute. You should never try comparing `View` to `null`. Instead use `IsViewLoaded`, which checks without itself triggering a load.

Event Handlers and Cleanup
==========================

In order to avoid memory leaks or crashes it may be necessary to do some work when you view controller is about to be used and then clean up when it is no longer in use. For instance, you may register for some notifications, and in order to avoid leaking or crashing you need to unregister those notifications. The best methods to use for this are `ViewWillAppear` and `ViewDidDisappear`. Here is an example:

    :::csharp
    private NSObject _notificationHandle;

    public override void ViewWillAppear()
    {
        _notificationHandle = NSNotificationCenter.DefaultCenter.AddObserver(NotificationName, HandleNotification);
    }

    public override void ViewDidDisappear()
    {
        if (_notificationHandle != null)
        {
            NSNotificationCenter.DefaultCenter.RemoveObserver(_notificationHandle);
            _notificationHandle = null;
        }
    }

You should not use `ViewDidLoad` or `LoadView` for anything that needs to be cleaned up in `ViewDidDisappear` because it is possible (and even likely) that `ViewDidDisappear` will be called multiple times, but `ViewDidLoad` and `LoadView` will only ever be called once.

Some people like to put cleanup code in `Dispose(bool)`, but I think that is generally a bad idea for a few reasons. First, many people mistakenly believe that it will avoid leaks (see [this post](http://blog.adamkemp.com/2014/10/c-finalizers-and-idisposable.html). If you have to do cleanup in order to avoid leaking your view controller itself then the only way that `Dispose(bool)` will help is if you explicitly `Dispose()` your view controller somewhere, which is error prone. If you are cleaning up other resources, like background tasks, then it may not even be safe to wait that long. Personally I think it is wrong to use `Dispose(bool)` for anything other than cleaning up _unmanaged_ resources. Everything else should be handled using `ViewWillAppear` and `ViewDidDisappear` or possibly custom app-specific life cycle methods.

In a future blog post I will cover memory leak avoidance for event handlers in Xamarin.iOS in more detail.
