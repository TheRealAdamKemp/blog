<!-- !b
kind: post
service: blogger
title: View Controller Lifecycle
labels: mobile, ios, xamarin, view controller, UIViewController, lifecyle
draft: True
-->

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aliquam nibh nunc, egestas quis enim mattis, ultrices dignissim erat. Etiam ac laoreet erat, tincidunt rhoncus nulla. Sed accumsan quam non dolor euismod fermentum. Sed non eros consectetur, aliquet massa ut, pellentesque mauris. Suspendisse id purus in ex mollis vestibulum sed sed eros. Phasellus dictum vel ante quis vehicula. Sed non metus lacus. Nunc mattis turpis tortor, vel gravida dui rhoncus ultricies. Maecenas aliquet libero vestibulum leo efficitur elementum. Nam aliquet pretium nisi, eget congue nisi sagittis et. Morbi cursus venenatis metus vitae scelerisque.

<!--more-->

[TOC]

View Controller Life Cycle
==========================

View controllers have a slightly more complex life cycle than views, and it may not be clear what should be done at each state of that life cycle. Here are some of the stages:

* Construction
* `LoadView`
* `ViewDidLoad`
* `ViewWillAppear`
* `ViewWillLayoutSubviews`
* `ViewDidLayoutSubviews`
* `ViewDidAppear`
* `ViewWillDisappear`
* `ViewDidDisappear`

When a view controller is first constructed it doesn't have a view. That means you should not try to access the `View` property from within the constructor[^viewInConstructor]. It also means that you should write your public API carefully

[^viewInConstructor]: Technically you can access the `View` property in a constructor, but doing so will trigger calls to `LoadView` and `ViewDidLoad`, which may assume that the code in the constructor has already run. This is very likely to cause problems and so it is a good idea to avoid it.
