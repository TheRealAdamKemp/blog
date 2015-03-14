<!-- !b
kind: post
service: blogger
title: Decoupling Views
url: http://blog.adamkemp.com/2015/03/decoupling-views.html
labels: mobile, ios, android, xamarin, decoupling, software-engineering, xamarin-forms
blog: 6425054342484936402
draft: False
id: 1425081000072361464
-->

One of the most common design mistakes that I see people make in mobile applications is coupling their views together. In this post I will explain why this is a problem and how to avoid it.

<!--more-->

The most common form of coupling one view to another is by making it aware of where it fits within the whole flow of the app. For instance, a common navigational pattern in mobile apps is to launch with a login screen and then transition to a main screen after a successful login. A naive implementation of this pattern would be to have the code for the login page directly do the transition to the main page. However, this is the wrong approach.

[TOC]

Why is Coupling Views Bad?
====================

First, for those who may not have taken a software engineering course, what is coupling? [Coupling](http://en.wikipedia.org/wiki/Coupling_(computer_programming)) in its most basic form is when one component depends on another directly. As an example, if class `A` directly interacts with class `B` (i.e., by using variables of type `B`) then `A` is coupled to `B`. If `B` changes then `A` is affected, and if you want to replace `B` with `C` then you have to update `A`.

It is generally accepted in software engineering that coupling is a Bad Idea. I'm not going to try to give a detailed justification for this here because it's usually not controversial, but I do want to justify why I think specifically coupling of _views_ is a Bad Idea. For that let me go back to the more concrete example from my introduction: consider an app with a login screen and a main screen. In your initial implementation you start with a login screen on launch, and then on a successful login the login screen itself transitions to the main screen. In Xamarin.Forms[^ViewController] that may look like this:[^ViewModel]

    :::csharp
    public class LoginPage : ContentPage
    {
        // This method is called upon a successful login
        private async Task OnLoginSucceeded()
        {
            await Navigation.PushModalAsync(new MainPage());
        }
    }

[^ViewController]: The examples in this post are for Xamarin.Forms, but the same advice applies to other frameworks as well, including direct iOS and Android programming (using Xamarin.iOS/Xamarin.Android or their native languages). In fact, this advice is one of the major reasons that I strongly discourage the use of Storyboards in iOS.

[^ViewModel]: These examples put the navigational logic in the `Page`, which is contrary to my [previous blog post](http://blog.adamkemp.com/2014/09/navigation-with-mvvm_8.html). The same concepts apply regardless of whether the navigation is in the `Page` or the `Page`'s view model. The examples are just simpler this way.

Given code like this here are some questions that we need to ask:

1. Is modal navigation the right mechanism or is there another way to transition to the next page? Maybe a `NavigationPage` would be more appropriate, or perhaps just setting the `MainPage` property of the application.
2. Is `MainPage` the only possible next page to show? Maybe in some cases you are taken directly to another page.
3. Does a successful login always need to push a new page at all? Maybe in some cases the login page is itself presented modally, and it merely needs to be popped.

Each of these questions is a hint that the line of code above may not cover some use cases or may need to change in the future. Put another way, each of these tells us that we are coupling the login page to a specific set of assumptions. That coupling is a barrier to progress.

Writing Decoupled Views
=======================

Now that we've identified the problem we need to figure out how to solve it. The trick to avoiding coupling of views is to make the views as dumb as possible. Consider again the login page. What does a login page need to do? Just one thing: allow the user to enter credentials and verify those credentials[^MVVM]. There are typically only two possible results of a login page: (1) success or (2) failure. Therefore the login page only needs to provide the ability to communicate success or failure.

[^MVVM]: I am ignoring here another possible pitfall: the view itself (the `LoginPage` above) should not be doing any verification of credentials. In a proper MVVM architecture the view (the page in this case) should only be responsible for displaying information to the user and getting input from the user. The model should be doing the actual authentication.

At this point you may be wondering "communicate to _whom_?" or "communicate _how_"? The simple, if unhelpful, answer to the first question is "whoever wants to know". Making assumptions about who wants to know about a successful login risks introducing yet more coupling. The real question then is how to communicate to an unknown interested party, and so the more important question is the second: _how?_

There are many ways of dealing with the problem of sending messages to unknown interested parties in software, and they mostly fall under the [Observer Pattern](https://msdn.microsoft.com/en-us/library/ee817669.aspx#observerpattern_topic3a). In C# the easiest way to implement this pattern is with [C# events](https://msdn.microsoft.com/en-us/library/aa645739(v=vs.71).aspx)[^MessageCenter]. Applying that to our login example we would change our code to something like this:

    :::csharp
    public class LoginPage : ContentPage
    {
        public event EventHandler LoginSucceeded;

        public event EventHandler LoginFailed;

        private void OnLoginSucceeded()
        {
            if (LoginSucceeded != null)
            {
                LoginSucceeded(this, EventArgs.Empty);
            }
        }

        private void OnLoginFailed()
        {
            if (LoginFailed != null)
            {
                LoginFailed(this, EventArgs.Empty);
            }
        }
    }

[^MessageCenter]: In Xamarin.Forms you could also use `MessageCenter` to broadcast messages, but in more complex examples you may end up with multiple instances of the same kind of page in existence, and subscribers would then have to be sure to handle only the messages from the page they're actually interested in. Not only is that error prone, but in order to do that discrimination the subscriber has to have a direct reference to the sender in the first place, and then you may as well just be using events. Events are just easier for this use case. Use `MessageCenter` for cases where it really is a broadcast to the whole system.

Now we have a login page that knows nothing about what to do after logging in, but we still have to somehow do something in response to the user logging in. Where does that code go now? The most likely candidate is the code that presented the login screen in the first place. For instance, typically an app will start with a login screen and then after a successful login transition to a main page. That code might live in the `Application` class, and it might look like this:

    :::csharp
    public class App : Application
    {
        public App()
        {
            var loginPage = new LoginPage();
            loginPage.LoginSucceeded += HandleLoginSucceeded;
            MainPage = loginPage;
        }

        private void HandleLoginSucceeded(object sender, EventArgs e)
        {
            MainPage = new MainPage();
        }
    }

Later you may decide you prefer doing that transition as a modal push instead. To change that you just need to change the `HandleLoginSucceeded` method like this:

    :::csharp
    private async void HandleLoginSucceeded(object sender, EventArgs e)
    {
        await MainPage.Navigation.PushModalAsync(new MainPage());
    }

Or maybe you want to present the login page on top of the main page itself and then dismiss it after success:

    :::csharp
    private async void HandleLoginSucceeded(object sender, EventArgs e)
    {
        await MainPage.Navigation.PopModalAsync();
    }

The advantage is that this change doesn't affect any other possible uses of `LoginPage` (current or future). The code that knows how `LoginPage` is presented is the same code that knows how to transition away from the login page.

Summary
=======

Implementing views that are decoupled gives you greater flexibility and makes it easier to reuse views for multiple use cases. You should try to avoid directly presenting a new view from within a view itself and consider moving that code outside of the view.

In a future post I will take this idea further and explore how to manage more complex navigation flows with decoupled views.
