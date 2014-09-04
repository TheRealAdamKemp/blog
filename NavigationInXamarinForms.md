<!-- !b
kind: post
service: blogger
title: Navigation in Xamarin.Forms
url: http://blog.adamkemp.com/
labels: mobile, navigation, xamarin.forms, ios, android
blog: 6425054342484936402
draft: True
id: 8448255091863454314
-->

Navigation is a fundamental concept in mobile applications. Desktop computers have relatively large screens that lend themselves to many modeless windows, which allows users to see multiple views at once switch between tasks quickly. Mobile devices, on the other hand, have small screens. It would be impractical in most cases to show multiple views at once (no matter what Samsung's marketing says). As a result, mobile applications tend to be designed around the concept of moving from one full-screen view to another. In this post I'll describe the most common types of navigation in mobile apps and how to use them in Xamarin.Forms.

<!--more-->

[TOC]

Types of navigation
=====

Different mobile platforms provide different APIs and UIs for showing these full screen views and moving from one view to another, but a few common patterns have emerged.

*Modal* navigation is when one full screen view leads to another full screen view. No UI elements are shared between the original view and the new view. On a tablet the new view may actually only take up a subset of the screen (example: "form sheets" on iOS or "dialogs" on Android), but even in that case the view in the background is inaccessible. The user must interact with the new view until it is removed.

*Hierarchical* navigation is when a user is led through a series of two or more views with the ability to go back to previous screens. In most cases this is really just a specialized type of modal navigation. The key difference is that the user can always go back to the previous view using standard UI elements. For instance, on iOS there is a navigation bar (UINavigationBar) at the top of the view with a back button on the left. On Android a user can either press the OS back button or press the back button on the ActivityBar (if it is showing).

iOS also natively supports using hierarchical navigation nested in popovers. Currently Xamarin.Forms only supports full-screen modals (no form sheets or dialogs), and there is no support for popovers yet.

Which type to use?
=====

Since there are two ways of navigating from one page to another you may be wondering which one you should use. The answer to this depends on what you want the user to see and what he should be able to do.

Modal navigation is a good choice when you want a user to complete some task before continuing. For instance, if a user is entering data in a form and needs to either fill it out completely and post it or cancel then maybe you shouldn't allow him to press "back". That might confuse him about what would happen to the partially filled out form. Is it saved? Can he come back to it later? It's better in this case to use a modal screen with a "Save" (or "Post" or "Submit" or "Login" etc.) button and (maybe) a "Cancel" button. Apple does this for emails in iOS.

Using hierarchical navigation, on the other hand, implies that the user can go back  at any time. For instance, tapping on an artist name in a music app may present a list of albums by that artiest. Tapping on an album may present a list of songs. The user can always go back to the albums view when looking at a songs view, and he can also go back to the artists view when looking at albums.

If you find yourself wondering "how do I prevent the user  from going back?" then you probably should be using modal navigation.

Combining navigation types
=====

In many mobile applications you will find examples of both types of navigation. How does that work? In both types of navigation there is a concept of going to a new screen then going "back" (Note I don't say going "forward" because that might imply that you could go "back" and then go "forward" again, and that's not always the case. Think of "back" as "undo"). If your application goes from screen A to screen B using modal navigation and then goes to screen X using hierarchical navigation then there are two possible choices for going "back". How does that work?

Conceptually you can think of your application as having two independent stacks: the modal stack and the hierarchical stack[^1]. When you perform a navigation from one screen to another you are "pushing" a new view onto one of those stacks. Since there are two stacks you can pop from either one.

[^1]: This is technically only true for apps that have only full screen view navigation, and even then probably only mostly true, but it's close enough for our purposes.

However, it's slightly more complicated than that. Each modally-presented view actually has its own hierarchical navigation stack. Consider the following flow of screens:

A --(hierarchical)--&gt; B --(modal)--&gt; X --(hierarchical)-&gt; Y

After that flow you are looking at screen Y. There are two options for going "back" which you could expose as two different UI options. Let's say you have a "cancel" button that pops the modal stack. In that case you return to screen B, and screen A is still available as an option to go back to. Screen X would be lost along with screen Y. Alternatively, if the user instead presses "back" from screen Y then he would return to screen X.

Popping a modal view throws away any hierarchical view stack that may have existed.

Implementing in Xamarin.Forms
=====

It's possible that all of that seemed obvious to everyone, but the reason I went through the explanation is that I've seen a lot of confusion among new Xamarin.Forms users about which type of navigation to use and how the API works. That's because in Xamarin.Forms there are actually two orthogonal sets of functions relating to navigation combined into one interface: INavigation. These are the functions:

* Modal navigation: 
    * `PushModalAsync`
    * `PopModalAsync`
* Hierarchical navigation:
    * `PushAsync`
    * `PopAsync`
    * `PopToRootAsync`

The first thing to remember here is that the "modal" functions go together, and the other ones go together. That is, if you push a view using "`PushModalAsync`" then you must pop it using "`PopModalAsync`". Likewise, if you push using "`PushAsync`" then you have to pop using "`PopAsync`" or "`PopToRootAsync`". Why is there no "`PopModalToRootAsync`"? There could be in theory (I think), but modal navigation generally doesn't work that way so it's not provided.

The second thing to consider is that hierarchical navigation requires special UI for the back button. Where does that UI come from? It comes from a special kind of page called `NavigationPage`. Therefore in order to use hierarchical navigation (i.e., in order to use `PushAsync`) you have to have a` NavigationPage`. This is the thing that actually keeps track of the hierarchical navigation stack, and it is responsible for putting the UI on the screen for going back to the previous page.

`NavigationPage` is easy to use. All you do is take your existing page and wrap it in a `NavigationPage` by calling the single-argument constructor like so:

    :::csharp
    NavigationPage navigationPage = new NavigationPage(originalPage);

Once you've done that you can use the `Navigation` property of either `navigationPage` or `originalPage` to call `PushAsync`, and the UI will automatically show you a back button to return to `originalPage`.

Other types of navigation
=====

While modal and hierarchical navigation are the most common in mobile apps, there are a few other types that are commonly used as well. Some other common types you will see include:

* Tab navigation
* Master/detail

I won't go into detail about those types here, but it's good to know that they exist. I may cover these in a future post. I will, however, point out that each of these can be combined as well with either modal or hierarchical navigation. For instance, you can present a tabbed interface modally, or you can present a modal view from a tabbed interface. Likewise, a single tab may contain hierarchical navigation within it, or the master or detail view may have hierarchical navigation.

You can combine all of these forms of navigation together in complex ways. When doing so try to keep these things in mind. First, the organization of the UI (the flow of screens) should be determined based on what makes sense to the user. The APIs usually support nearly any combination you can think of, but a user has to understand at all times what the options in the UI mean. For instance, if you have navigation nested in a tab then will he understand clearly what "back" will do?

Second, remember that each `NavigationPage` has its own hierarchical stack, but there is currently only one modal stack in Xamarin.Forms. If push a view modally then it replaces the whole screen. If you push a view onto a `NavigationPage` then it replaces only the view within that `NavigationPage`.
