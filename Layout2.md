<!-- !b
kind: post
service: blogger
title: iOS Layout Gotchas Redux
url: http://blog.adamkemp.com/2014/12/ios-layout-gotchas-redux.html
labels: ios, layout, mobile, xamarin
blog: 6425054342484936402
draft: False
id: 1888251753431542710
-->

Since my [last post on iOS Layout Gotchas](http://blog.adamkemp.com/2014/11/ios-layout-gotchas-and-view-controller.html) I have encountered a few more basic layout mistakes that can lead to bugs and brittle code. Some of these are things I have found myself doing so hopefully they will be useful to others.

<!--more-->

[TOC]

Don't use the parent's center
=============================

I have seen (and even written) code like this:

    :::csharp
    var parent = child.Superview;
    child.Center = child.ConvertPointFromView(parent.Center, parent);

This code does handle coordinate systems properly (see my [previous post](http://blog.adamkemp.com/2014/09/uiview-frame-vs-bounds.html#coordinate-systems)), but it is still brittle code. To see why let's first consider what the intent is. What we're trying to do is center the child in its parent. The code makes sense because it is just saying that the center of the child should be the same as the center of the parent (translated into the child's coordinate system). The problem is that this code is assuming that the parent already has a valid center. That is, this code assumes that layout has already been done for the _grandparent_ (most likely the view responsible for positioning the parent). That may not always be the case.

Aside from explicit requests for layout (via `SetNeedsLayout`), layout typically happens in a given view because its size has changed. When its size changes it redoes layout to position its children. If the size doesn't change then layout probably won't happen (even if the position does change). That means it is possible for the size of the parent to be set and trigger layout _before_ it has a position. The position may change later (meaning its `Center` may change) without going through laying out its children.

Basically what that means is you should never trust the `Center` property of a view's parent unless you're the one who set it. Instead you should use the `Bounds` of the parent view:

    :::csharp
    var parent = child.Superview;
    var parentBounds = parent.Bounds;
    child.Frame = new CGRect
    {
        X = (int)((parentBounds.Width - width) / 2),
        Y = (int)((parentBounds.Height - height) / 2),
        Width = width,
        Height = height,
    };

Notice that I switched to using `Frame`, and I cast to an `int`. For an explanation see the next item.

Avoid misaligned views
======================

On iOS the layout and rendering system uses floating point values for size and position. This is nice because it allows for transforms and coordinate systems so that views don't have to be exposed to things like the pixel density of the device. Everything works in generic "points", and somehow that gets rendered to the screen. However, at some point those points are converted to actual pixels, and pixels are discrete things. If you want a line that is precisely one pixel thick then you need to make sure that it falls precisely on a pixel boundary. Otherwise it will get anti-aliased, and it will look blurry. In fact, for any view if the position of that view does not fall on a pixel boundary when it is rendered then that view will be anti-aliased. This can result in the whole view being blurry, which is especially noticeable in text on non-retina devices. To find these kinds of problems easily you can run your app in the simulator and then choose the "Color Misaligned Images" option from the "Debug" menu. It will color any problematic views in purple (ignore the yellow views; they represent a different situation, and in most cases that is expected and benign).

The most common way to end up in this situation is with centering code like the previous example. Consider this naive implementation:

    :::csharp
    var parent = child.Superview;
    var parentBounds = parent.Bounds;
    child.Frame = new CGRect
    {
        X = (parentBounds.Width - width) / 2,
        Y = (parentBounds.Height - height) / 2,
        Width = width,
        Height = height,
    };

This is a common way to center a view, and it technically gets the exact right answer. If the width of the parent is `10` and the width of the child is `5` then the X position of the child should be `2.5` (`(10 - 5) / 2 = 5/2 = 2.5`). However, `2.5` is not on a pixel boundary, which means this view will be anti-aliased. You don't want that. The simple fix is to truncate the X and Y after centering, which would possibly make it a half pixel off center, but that avoids the anti-aliasing and is in almost every case totally unnoticeable.

What do you do if you have to use the `Center` property? Well that gets a little trickier. It seems simple. Again, the naive implementation is this:

    :::csharp
    var parent = child.Superview;
    var parentBounds = parent.Bounds;
    child.Center = new CGPoint
    {
        X = parentBounds.Width / 2,
        Y = parentBounds.Height / 2,
    }

You might think after looking at the previous fixed example that all you need to do here is truncate X and Y, but that would be wrong as well. To see why consider what happens if the parent's width is `15` and the child's width is `5`. If you center with the above code then you will get a center X of `7`, which would put the top-left X at `4.5` (`7 - (5/2) = 7 - 2.5 = 4.5`). That's not a pixel boundary! That might make you think you should just force it to always be a half-pixel, but that would be wrong too. Generally speaking, whether the center should be a integer or not depends on whether the size of the child is even or not. That makes just setting the center complicated. To make this easier I wrote an extension method that does the right thing:

    :::csharp
    public static void SafeSetCenter(this UIView view, CGPoint center)
    {
        var size = view.Bounds.Size;
        center = center.Floor();
        if ((int)size.Width % 2 != 0)
        {
            center.X += 0.5f;
        }
        if ((int)size.Height % 2 != 0)
        {
            center.Y += 0.5f;
        }

        view.Center = center;
    }

(This relies on another extension method for `CGPoint` to floor both X and Y, but that is trivial to write).

What this function does is first truncate the given center and then optionally add back half a pixel to each component if necessary. This code does not handle non-integral sizes, but that's usually a bad idea so I just ignore it.

To use this code you would modify the previous example like this:

    :::csharp
    var parent = child.Superview;
    var parentBounds = parent.Bounds;
    child.SafeSetCenter(new CGPoint
    {
        X = parentBounds.Width / 2,
        Y = parentBounds.Height / 2,
    });

Since centering a view within its parent is an especially common operation I also made an extension method for that specific case:

    public static void CenterInParent(this UIView view)
    {
        var parent = view.Superview;
        if (parent == null)
        {
            throw new InvalidOperationException("Cannot center a view in its parent unless it has a parent");
        }
        var parentSize = parent.Bounds.Size;
        view.SafeSetCenter(new CGPoint(parentSize.Width / 2, parentSize.Height / 2));
    }

Now to use that you could just write this code:

    :::csharp
    child.CenterInParent();

Don't call `LayoutSubviews` directly
====================================

The iOS layout system is designed to be mostly asynchronous to avoid doing extra work. When you need layout to happen you call `SetNeedsLayout`, and at some later time the `LayoutSubviews` method will be called. However, sometimes you need to ensure that layout happens synchronously. Usually this comes up when dealing with animations. If you make a change that affects layout, and you want that change to be animated, then you may need to force a synchronous layout within the animation block (or maybe force it before the animation so that the first layout is not part of the animation). To force a layout you should never call `LayoutSubviews` directly. Instead you should call `LayoutIfNeeded`, which will do a synchronous layout only if the view is marked as needing layout.

Still, there are times when you need to force a layout to happen synchronously _always_ (as in, you need to tell it "you have a change that requires redoing layout, _and_ I want you to do that layout right now instead of later). In those situations I have previously made the mistake of thinking that I should just call `LayoutSubviews` directly. After all, if you call `SetNeedsLayout` immediately followed by `LayoutIfNeeded` then you might expect those two lines to have the same effect as a single call to `LayoutSubviews`. Why not write just the one line? However, it turns out that the two lines don't do exactly the same thing as the one. Specifically, `LayoutSubviews` does one and only one thing: it lays out the subviews for _that one_ view. It doesn't force layout recursively on all of the descendants of that view. But if you are needing layout to happen synchronously then you almost certainly want it to happen for all descendants as well. The function that does that is `LayoutIfNeeded`. Therefore, if you really want to force layout to happen and you want it done synchronously then you should call both functions like this:

    :::csharp
    view.SetNeedsLayout();
    view.LayoutIfNeeded();

If you only require that layout happen synchronously if necessary, but you don't need to force it to happen if it wasn't already necessary then you just need the one line:

    :::csharp
    view.LayoutIfNeeded();

In any case you should never call `LayoutSubviews` directly on any view (even your own subviews). Just let the layout system do its job.

Don't set your own `AutoresizingMask`
=====================================

This is a special form of violating the "Top-Down Principle" I described in my [previous post](http://blog.adamkemp.com/2014/11/ios-layout-gotchas-and-view-controller.html#the-top-down-principle). This principle is that only the owner of a view (usually its parent view) should set the size and position of that view. The view should never set its own size and position. `AutoresizingMask` is a way of causing a view to grow or move along with its parent, which has the effect of setting that view's size and position automatically. That is still a decision that should be left to the parent, though. I have encountered code recently in which a view was setting its own `AutoresizingMask`, effectively deciding for that view how it will behave within its parent. The result is that the parent is no longer in control, and that can make changing the layout process difficult. For instance, I was trying to do a specific animation, and because the view had asserted this relationship between its size/position and its parent's I was not able to get the effect I wanted. The fix was to remove the `AutoresizingMask` line. If that code had been in the parent in the first place then that would have been easy to determine, but instead I spent quite a bit of time trying to figure out why the animation was misbehaving.

The `AutoresizingMask` is a layout trait just like `Bounds`, `Center`, and `Frame`, and it should be the responsibility of the owner alone to set those properties.
