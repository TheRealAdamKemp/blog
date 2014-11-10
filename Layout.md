<!-- !b
kind: post
service: blogger
title: iOS Layout Gotchas and View Controller Life Cycle
url: http://blog.adamkemp.com/2014/11/ios-layout-gotchas-and-view-controller.html
labels: mobile, ios, xamarin, layout
blog: 6425054342484936402
draft: False
id: 758594618750689537
-->

In a previous post I touched on layout in iOS by describing [the difference between `Frame` and `Bounds`](http://blog.adamkemp.com/2014/09/uiview-frame-vs-bounds.html), and in that post I covered one of the most common layout mistakes I encounter in iOS code. However, there are several other common mistakes in layout that I have been seeing a lot recently. Read on to learn how to avoid these gotchas in your own code.

<!--more-->

[TOC]

The Top-Down Principle
======================

The most general rule of layout is this: layout should always be done top-down. What I mean by that is that the size and location of a view should only ever be set by the _owner_ of that view. Put another way, you should never set the `Frame` of a view that you didn't create yourself.

Let's consider a few concrete examples of some common violations of this rule.

Violation 1
-----------

    :::csharp
    public class MyView : UIView
    {
        public MyView(CGRect frame)
        {
            Frame = new CGRect(0, 0, 50, 50);
        }
    }

In this example you can see that we have a custom view, and in the constructor for that view it sets its own `Frame`. __Never set your own `Frame`__. Recall the rule: don't set the `Frame` of a view that you didn't create. A view can't create itself so it shouldn't set its own `Frame`. The size and location of a view is something that only its creator should set.

Violation 2
-----------

    :::csharp
    public class MyViewController : UIViewController
    {
        // ...

        public override void ViewDidLoad()
        {
            View.Frame = UIScreen.MainScreen.Bounds;

            // ...
        }
    }

This is a similar example as the first one, but in this case we are using a view controller instead of a view. Some people seem to think that view controllers don't have to follow the same layout rules as views, but they are wrong. __A view controller does not control its layout__. I will discuss view controllers more later in this article.

Violation 3
-----------

    :::csharp
    public class MyView : UIView
    {
        private readonly MyOtherView _myOtherView;

        // ...

        public override void LayoutSubviews()
        {
            base.LayoutSubviews();

            _myOtherView.Frame = Bounds;
            _myOtherView.SomeSubview.Frame = Bounds;
        }
    }

This example shows a violation from the other direction. In this case we are not setting our own `Frame`, but we are setting the `Frame` of a view that we don't own: `_myOtherView.SomeSubview` belongs to `_myOtherView`. Presumably the `LayoutSubviews` override in `MyOtherView` will set `SomeSubview`'s `Frame`. We should not be subverting its layout decisions. This is a good way to end up with subtle bugs where two pieces of code fight over how to do layout.

Defer Layout Until the Layout Overrides
=======================================

Another common mistake in layout is trying to do layout too early. There are a few key locations where layout should be performed:

* For a `UIView` subclass use `LayoutSubviews`.
* For a `UIViewController` subclass use `ViewDidLayoutSubviews`.

These methods exist specifically to give you an opportunity to do layout. If you try to do layout _before_ these methods then you are likely to base your layout on invalid information.

Violation 1
-----------

    :::csharp
    public class MyView : UIView
    {
        public MyView(CGRect frame) : base(frame)
        {
            AddSubview(new MyOtherView(Frame));
        }
    }

This is a very common mistake, and it happens because people get lazy. You can see that we are creating a new view (`MyOtherView`), giving it a size, and adding it as a subview all in one line in our constructor. It's so easy, right? It's also wrong. What happens when your `Frame` changes? That subview won't change size. This code assumes a static size set at the time of construction, but as we learned previously our size and position are owned by our creator, and therefore our creator can change our size and position at any time.

Here is the corrected code:

    :::csharp
    public class MyView : UIView
    {
        private readonly MyOtherView _myOtherView;

        public MyView()
        {
            _myOtherView = new MyOtherView();
            AddSubview(_myOtherView);
        }

        public override void LayoutSubviews()
        {
            base.LayoutSubviews();

            _myOtherView.Frame = Bounds;
        }
    }

Now we assign our subview to a field, and we defer the layout to the proper layout method (`LayoutSubviews`). Yes, this is slightly more work, but it is also much more robust. As a bonus you may have noticed that I set our subview's `Frame` to our own `Bounds`, whereas in the incorrect code we were using our own `Frame`. If you need a refresher on what the difference is then refer to my [earlier post](http://blog.adamkemp.com/2014/09/uiview-frame-vs-bounds.html).

I also want to point out another subtle change: I removed the `CGRect frame` argument from the constructor. Having that argument in `UIView`'s constructor was, in my opinion, a mistake on Apple's part. It encourages people to write incorrect code by trying to merge the act of view creation with the act of view layout. Those two tasks do not belong together. If you include that parameter then not only will you be tempted to use that argument within your constructor (which we just learned is wrong), but you will also be encouraging your clients to use it (which they shouldn't do). I really hate writing code like this:

    :::csharp
    _myView = new MyView(CGRect.Empty);

That's just noisy code. It should just be this:

    :::csharp
    _myView = new MyView();

Do yourself a favor and don't follow Apple's example. Don't include a frame argument in your custom view constructors.

Violation 2
-----------

    :::csharp
    public class MyViewController : UIViewController
    {
        // ...

        public override void ViewDidLoad()
        {
            base.ViewDidLoad();

            View.AddSubview(new MyView() { Frame = View.Bounds });
        }
    }

This should look very familiar. It is, in fact, the view controller analogue of the previous example. In this case, just as before, we are trying to set the `Frame` of a view we just created. Instead, we should be deferring that work until later.

This mistake is actually very common, and it often goes unnoticed for a while. The reason is that often `View.Bounds` will have a perfectly reasonable value in `ViewDidLoad`. Frequently that size comes from the .xib, and so it will be whatever size the .xib was designed for (often portrait screen size). This bug is usually discovered in one of the following scenarios:

* The screen size changes. A lot of people ran into this when updating their apps for the taller iPhone 5, and probably many more ran into it when updating their apps for the iPhones 6.
* Adding iPad support (a variation on the screen size changing).
* Rotation (also technically a variation of the screen size changing).

All of these expose the same invalid assumption: the initial size of a view controller's view is not necessarily the correct size. It may change later (remember rule 1: the owner of the view owns the size of that view). I will go into more detail about view controllers in a future article.

Here is the corrected code, which should again look very familiar:

    :::csharp
    public class MyViewController : UIViewController
    {
        private MyView _myView;
        // ...

        public override void ViewDidLoad()
        {
            base.ViewDidLoad();

            _myView = new MyView();

            View.AddSubview(_myView);
        }

        public override void ViewDidLayoutSubviews()
        {
            base.ViewDidLayoutSubviews();

            _myView.Frame = View.Bounds;
        }
    }

This is the same pattern as I used when fixing the first example, but it is adapted for a view controller.

Never Use `UIScreen`'s Size For Layout
======================================

Another common mistake I see is trying to use the size of the screen to do layout. This typically happens in conjunction with a violation of the first rule. For example, look again at the second example from above:

    :::csharp
    public class MyViewController : UIViewController
    {
        // ...

        public override void ViewDidLoad()
        {
            View.Frame = UIScreen.MainScreen.Bounds;

            // ...
        }
    }

We already discussed why you shouldn't be setting your own `Frame` here, but let's consider why you shouldn't use the screen's bounds. The primary reason is that it violates the principle of top-down layout. When you use the screen size here you are assuming that this view will always fill the screen (or fill some fixed portion of the screen). That's a problem because it makes this view controller (or view) hard to reuse. It's not adaptable. View controllers can be presented full screen, but they can also be presented as form sheet modals, page sheet modals, in popovers, in slide-out views, and so on. View controllers should adapt to the environment they are put in, just like custom subviews. Whenever possible you should base your layout logic on whatever size your view actually has rather than pinning it to the size of the whole screen.

That said, there are times when a view controller really is designed specifically to fill the screen, and that is all that view controller will ever be used for. You may find yourself wanting to precisely lay out the views for a specific screen size. I have spent most of my iOS development time working on iPad applications, and we have the luxury (so far) of making assumptions about how many points (device-independent pixels) there are on the screen and very carefully laying out our views to take advantage of the screen real estate. For instance, if you look at the view in [VirtualBench](https://itunes.apple.com/us/app/virtualbench/id896797834?mt=8) (an app I worked on) you will see an example of a very carefully designed UI. We chose every font size, margin, and view size specifically for a landscape iPad view size because that's the only view size we needed to support. In cases like this you _still_ shouldn't use `UIScreen.MainScreen.Bounds`. Instead you should just use your own hard-coded constants. The reason for that is that `UIScreen.MainScreen.Bounds` could still change! It's a variable, after all. It's not a constant. If your layout depends on a constant then use a constant.

This is not a hypothetical concern. In fact, as I mentioned in a [footnote](http://blog.adamkemp.com/2014/09/uiview-frame-vs-bounds.html#fn:iOS8) in my previous article, in iOS 8 the meaning of `UIScreen.MainScreen.Bounds` did in fact change. Previously (7.x and earlier) the screen's `Bounds` were fixed to a certain size regardless of the interface orientation. That is, as you rotated the device the app's view would rotate around (swapping its width and height), but the screen's `Bounds` never changed size (or origin). Starting in iOS 8, though, the screen's `Bounds` _do_ change as you rotate the device. If you use code like you see in the bad example above then your view may get the wrong size depending on how the user is holding his device at the time.

This specific mistake may come up for people updating their code to use the iOS 8 SDK. I have been working on doing that for one of my projects, and I found several examples of this mistake in our code. As a result our views were in the wrong place. The fix was to use `View.Bounds` and do the layout work in `ViewDidLayoutSubviews` instead.

Summary
=======

These are the key takeaways from this article:

1. Never set your own `Frame` in a `UIView` or your own `View.Frame` in a `UIViewController`.
2. Do layout in `LayoutSubviews` in a `UIView` and in `ViewDidLayoutSubviews` in a `UIViewController`.
3. Don't use the screen's size for layout. Instead use `Bounds` in a `UIView` and `View.Bounds` in a `UIViewController`.
