<!-- !b
kind: post
service: blogger
title: Navigation With MVVM
labels: mobile, mvvm, navigation
draft: True
-->

In my [previous post](http://blog.adamkemp.com/2014/09/navigation-in-xamarinforms_2.html) I covered the basics of navigation patterns in mobile apps and the Xamarin.Forms navigation APIs. In this post I will cover architectural issues related to navigation in an app using the MVVM pattern.

<!--more-->

[TOC]

The Problem
=====

[MVVM](http://en.wikipedia.org/wiki/Model_View_ViewModel) is a powerful design pattern for implementing cross-platform applications with UIs. Xamarin.Forms is based on MVVM, and it owes much of its portability to that pattern. The intent of MVVM is to try to separate platform-specific view code from potentially reusable logic (which may be model or view related). Typically you want to put as much logic into your View Model and model as you can (thus increasing your reusable/portable code) and keep your View very dumb. The View should just be about getting information on the screen and translating user input into events that can be handled by the View Model.

Navigation can be a bit of a challenge in MVVM because in theory the logic of which screen should be on the screen when is the domain of the View Model, but the APIs for actually moving from one screen to another are platform-specific[^platform]. This leads many people to putting their navigation logic in the View and then duplicating that logic for each platform.

[^platform]: Note that I am considering Xamarin.Forms to be a platform. When implementing a View you could many possible APIs, including raw Xamarin.iOS, Xamarin.Android, or Windows Phone APIs. Xamarin.Forms also lets you write view code using a specific API, but that API introduces a dependency that you may want to change in the future. If you use MVVM properly you should be able to reuse 100% of your Model and View Model even while switch between Xamarin.Forms and some other API.

In order to keep the navigation logic in the View Model where it belongs we need to solve a few problems:

1. Trigger the platform-specific navigation to that new View.
2. Create a new View given a new View Model (representing the new page/screen).

In order to accomplish this in the cross-platform View Model component we need some kind of interface and some dependency injection to get the platform-specific implementation.

My Solution
=====

I have created an example implementation of this approach. You can view the [source code](https://github.com/TheRealAdamKemp/Navigation) and an [example application](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests) on GitHub. Let's walk through how it works.

The core of this implementation is the `IViewModelNavigation` interface. It has the following methods:

    :::csharp
    public interface IViewModelNavigation
    {
        Task<object> PopAsync();

        Task<object> PopModalAsync();

        Task PopToRootAsync();

        Task PushAsync(object viewModel);

        Task PushModalAsync(object viewModel);
    }

If you read my last post or have used the Xamarin.Forms navigation then this interface will look familiar. That's because I just copied the `INavigation` interface from Xamarin.Forms and then changed all of the `Page` arguments to `object viewModel`. As a result there is nothing in this interface that is Xamarin.Forms specific. It could be used on any platform. This allows you to create your View Model with navigation logic and then swap out all of your view code. Xamarin.Forms is portable, but maybe you prefer to have your Windows Phone apps use the native APIs for more flexibility.

We'll get to usage of that interface shortly, but first let's look at how you get an instance of this interface. In my example application take a look at App.cs:

    :::csharp
    public static Page GetMainPage()
    {
        var mainPageViewModel = new MainPageViewModel();
        // ...
        var navigationFrame = new NavigationFrame(mainPageViewModel);
        return navigationFrame.Root;
    }

This code is part of your View (the `App` class is platform-specific[^platform]). This is where the dependency injection comes from. Here we create an instance of the `NavigationFrame` class, which is the object that implements `IViewModelNavigation` for Xamarin.Forms applications. The constructor for `NavigationFrame` takes an initial view model (for the first screen). Once constructed we access the `Root` property, which is a `NavigationPage` (the basis for navigation in Xamarin.Forms) and return that as our app's main page.

The next thing to note here is that when we create the `NavigationFrame` we give it a View Model, not a `Page`. Xamarin.Form's `NavigationPage` class takes a `Page` (a View) for its first screen, but this API takes a View Model instead. It then creates the View (a `Page`) for you and uses that when constructing the `NavigationPage`.

Now that we have our first View on the screen how do we navigate to another view? Take a look at the HandleItemSelected method in the [MainPageViewModel class](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests/blob/master/RssTest/ViewModel/Pages/MainPageViewModel.cs):

    :::csharp
    private void HandleItemSelected(object parameter)
    {
        ViewModelNavigation.PushAsync(new ItemPageViewModel() { Item = parameter as RssItem });
    }

`ViewModelNavigation` is our `IViewModelNavigation` interface (more on that property soon), and you can see that we are calling one of the methods from that interface. Again, when we call this method we give it a View Model, not a View. The View Model is portable, whereas the View is not. We want this logic to stay in the View Model, but we want it to remain portable by keeping any View types out of it.

Where did this `ViewModelNavigation` property come from? If you look at the [`PageViewModel` base class](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests/blob/master/RssTest/ViewModel/Pages/PageViewModel.cs) you will see that we implement the `INavigatingViewModel` interface. This interface that looks like this:

    :::csharp
    public interface INavigatingViewModel
    {
        IViewModelNavigation ViewModelNavigation { get; set; }
    }

All it does is provide a property that allows the Navigation API to inject itself into any View Models that it is given. This is optional (you can use your own mechanism to pass around the `IViewModelNavigation` instance), but it makes things a bit easier. Again, this mirrors the `Navigation` property in the `VisualElement` class of Xamarin.Forms. The design of this API lets you write your navigation code in nearly the same way that you already did in Xamarin.Forms, but you can move that code from your View into your View Model.

So far we've seen how the first requirement (dependency injection) is solved, but what about the second? Somehow we need to be able to take a View Model and create a View for it. That requires a factory of some sort.

My implementation uses reflection to handle this. First, you need to set up the association between your View and your View Model. To do this you use the `RegisterViewModelAttribute` to decorate your View like this:

    :::csharp
    [RegisterViewModel(typeof(MainPageViewModel))]
    public partial class MainPage : ContentPage
    {
        // ...
    }

When the Navigation API initializes it searches through the loaded assemblies for these attributes and sets up a dictionary mapping ViewModel types to View types. Then, whenever it needs to create a View from a View Model it looks up the right type from the dictionary, constructs the new View, and assigns the View Model as the `BindingContext` of the newly created View. Then all it has to do is call the Xamarin.Forms navigation API to navigate to the new View.

That's basically all there is to it. With this approach you can now keep your navigation logic where it belongs and improve the portability of your code.

Downsides of My Solution
=====

One potential downside of my current approach is its use of reflection. Reflection is a powerful way of marking up code in a clean, declarative way that keeps things decoupled, but it also comes with a runtime cost. At startup we have to go through all the types that are loaded looking for those attributes. That takes time, and that time grows as your application grows. Eventually this may lead to an unacceptable startup time cost. As an alternative you could initialize this mapping more directly in your code.

Another thing to consider is that this API still assumes a specific style of navigation that is most applicable to mobile applications. View Models can be very portable, but they still represent views. An application that is portable between desktop and mobile platforms may share all of the Model layer, but their UX is almost certainly very different. It doesn't make sense to try to share the View Model layer between radically different UX implementations. The navigation logic should likewise be portable between mobile applications or between desktop applications, but not between both. Therefore if you keep your navigation logic in your View Model you will have yet another reason to not try to share your View Models between desktop and mobile.
