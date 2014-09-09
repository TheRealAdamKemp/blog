<!-- !b
kind: post
service: blogger
title: Navigation With MVVM
url: http://blog.adamkemp.com/2014/09/navigation-with-mvvm_8.html
labels: mobile, mvvm, navigation, xamarin.forms, ios, android
blog: 6425054342484936402
draft: False
id: 4807419008631949832
-->

In my [previous post](http://blog.adamkemp.com/2014/09/navigation-in-xamarinforms_2.html) I covered the basics of navigation patterns in mobile apps and the Xamarin.Forms navigation APIs. In this post I will cover architectural issues related to navigation in an app using the MVVM pattern and one method of implementing your navigation in a more portable way.

<!--more-->

[TOC]

The Problem
=====

[MVVM](http://en.wikipedia.org/wiki/Model_View_ViewModel) is a powerful design pattern for implementing cross-platform applications with UIs. Xamarin.Forms is based on MVVM, and it owes much of its portability to that pattern. The intent of MVVM is to try to separate platform-specific view code from potentially reusable logic (which may be model or view related). Typically you want to put as much logic into your _View Model_ and _Model_ as you can (thus increasing your reusable/portable code) and keep your _View_ very dumb. The _View_ should just be about getting information on the screen and translating user input into events that can be handled by the _View Model_.

If you implement the MVVM pattern correctly then you should be able to put your _Model_, _View Model_, and _View_ each into their own assemblies. The _View Model_ assembly should not reference the _View_ assembly, and the _Model_ assembly should not reference either the _View_ or _View Model_ assemblies. In a Xamarin.Forms application only the _View_ assembly should include a reference to Xamarin.Forms[^reference]. That way both the _Model_ and _View Model_ could be reused with no code modification while swapping out the _View_ assembly (maybe to one that uses Windows Phone APIs directly).

[^reference]: In practice this may be harder than I would like it to be. There are some useful types in Xamarin.Forms, like `Command`, that would require more work to decouple. Still, it is possible using more dependency injection.

Navigation can be a bit of a challenge in MVVM because in theory the logic of which screen should be on the screen when is the domain of the _View Model_, but the APIs for actually moving from one screen to another are platform-specific[^platform]. This leads many people to putting their navigation logic in the _View_ and then duplicating that logic for each platform.

[^platform]: Note that I am considering Xamarin.Forms to be a platform. When implementing a _View_ you could many possible APIs, including raw Xamarin.iOS, Xamarin.Android, or Windows Phone APIs. Xamarin.Forms also lets you write view code using a specific API, but that API introduces a dependency that you may want to change in the future. If you use MVVM properly you should be able to reuse 100% of your _Model_ and _View Model_ even while switch between Xamarin.Forms and some other API.

In order to keep the navigation logic in the _View Model_ where it belongs we need to solve a few problems:

1. Create a new _View_ given a new _View Model_ (representing the new page/screen).
2. Trigger the platform-specific navigation to that new _View_.

In order to accomplish this in the cross-platform _View Model_ component we need some kind of interface and some dependency injection to get the platform-specific implementation.

My Solution
=====

I have created an example implementation of this approach. You can view the [source code](https://github.com/TheRealAdamKemp/Navigation) and an [example application](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests) on GitHub. Let's walk through how it works.

The core of this implementation is the `IViewModelNavigation` interface:

    :::csharp
    public interface IViewModelNavigation
    {
        Task<object> PopAsync();

        Task<object> PopModalAsync();

        Task PopToRootAsync();

        Task PushAsync(object viewModel);

        Task PushModalAsync(object viewModel);
    }

If you read my last post or have used the Xamarin.Forms navigation then this interface will look familiar. That's because I just copied the `INavigation` interface from Xamarin.Forms and then changed all of the `Page` arguments into _View Models_ (as type `object`). As a result there is no longer anything in this interface that depends on Xamarin.Forms. It could be used on any platform. This allows you to create your _View Model_ with navigation logic and then swap out all of your view code. Xamarin.Forms is portable, but maybe you prefer to have your Windows Phone apps use the more powerful native APIs.

We'll get to usage of that interface shortly, but first let's look at how you get an instance of it. In my example application take a look at App.cs:

    :::csharp
    public static Page GetMainPage()
    {
        var mainPageViewModel = new MainPageViewModel();
        // ...
        var navigationFrame = new NavigationFrame(mainPageViewModel);
        return navigationFrame.Root;
    }

This code is part of the _View_ (the `App` class is platform-specific[^platform]). This is where the dependency injection comes from. Here we create an instance of the `NavigationFrame` class, which is the object that implements `IViewModelNavigation` for Xamarin.Forms applications. The constructor for `NavigationFrame` takes an initial view model (for the first screen). Once constructed we access the `Root` property, which is a `NavigationPage` (the basis for navigation in Xamarin.Forms) and return that as our app's main page.

The next thing to note here is that when we create the `NavigationFrame` we give it a _View Model_, not a `Page`. Xamarin.Form's `NavigationPage` class takes a `Page` (a _View_) for its first screen, but this API takes a _View Model_ instead. It then creates the _View_ (a `Page`) for you and uses that when constructing the `NavigationPage`.

Now that we have our first _View_ on the screen how do we navigate to another view? Take a look at the HandleItemSelected method in the [MainPageViewModel class](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests/blob/master/RssTest/ViewModel/Pages/MainPageViewModel.cs):

    :::csharp
    private void HandleItemSelected(object parameter)
    {
        ViewModelNavigation.PushAsync(new ItemPageViewModel() { Item = parameter as RssItem });
    }

`ViewModelNavigation` is our `IViewModelNavigation` interface (more on that property soon), and you can see that we are calling one of the methods from that interface. Again, when we call this method we give it a _View Model_, not a _View_. The _View Model_ is portable, whereas the _View_ is not. We want this logic to stay in the _View Model_, but we want it to remain portable by keeping any _View_ types out of it.

Where did this `ViewModelNavigation` property come from? If you look at the [`PageViewModel` base class](https://github.com/TheRealAdamKemp/Xamarin.Forms-Tests/blob/master/RssTest/ViewModel/Pages/PageViewModel.cs) you will see that we implement the `INavigatingViewModel` interface. Here is the definition of that interface:

    :::csharp
    public interface INavigatingViewModel
    {
        IViewModelNavigation ViewModelNavigation { get; set; }
    }

All it does is provide a property that allows the Navigation API to inject itself into any _View Models_ that it is given. This is optional (you can use your own mechanism to pass around the `IViewModelNavigation` instance), but it makes things a lot easier. Again, this mirrors the `Navigation` property in the `VisualElement` class of Xamarin.Forms. The design of this API lets you write your navigation code in nearly the same way that you already did in Xamarin.Forms, but you can move that code from your _View_ into your _View Model_.

So far we've seen how the second requirement is solved (using dependency injection), but what about the first? Somehow we need to be able to take a _View Model_ and create a _View_ for it. That requires a factory of some sort.

My implementation uses reflection to handle this. First, you need to set up the association between your _View_ and your _View Model_. To do this you just use the `RegisterViewModelAttribute` to decorate your _View_ like this:

    :::csharp
    [RegisterViewModel(typeof(MainPageViewModel))]
    public partial class MainPage : ContentPage
    {
        // ...
    }

When the Navigation API initializes it searches through the loaded assemblies for these attributes and sets up a dictionary mapping _ViewModel_ types to _View_ types. Then, whenever it needs to create a _View_ from a _View Model_ it looks up the right type from the dictionary, constructs the new _View_, and assigns the _View Model_ as the `BindingContext` of the newly created _View_. It also assigns itself to the `ViewModelNavigation` property of the _View Model_ (if it implements `INavigatingViewModel`). Then all it has to do is call the Xamarin.Forms navigation API to navigate to the new _View_.

That's basically all there is to it. With this approach you can now keep your navigation logic where it belongs and improve the portability of your code.

Downsides of My Solution
=====

One potential downside of my current approach is its use of reflection. Reflection is a powerful way of marking up code in a clean, declarative way that keeps things decoupled, but it also comes with a runtime cost. At startup we have to go through all the types that are loaded looking for those attributes. That takes time, and that time grows as your application grows. Eventually this may lead to an unacceptable startup time cost. As an alternative you could initialize this mapping more directly in your code.

It also makes a classic tradeoff between portability and flexibility. The navigation API provided by this implementation is a bare-bones, lowest-common-denominator API that is supportable in some form by any mobile platform. There are many things you can do in platform-specific APIs that you can't do with this API. You could try to mitigate that by making a more extensible API, perhaps with a flexible mechanism of providing hints to the platform-specific implementation about how it might handle the navigation on each platform. The basic idea of using dependency injection and a _View_ factory is still useful, but there may be some middle ground when it comes to how much information about the platforms should leak into the API.

On a similar note, another thing to consider is that this API still assumes a specific style of navigation that is most applicable to mobile applications. _View Models_ can be very portable, but they still represent specific views. An application that is portable between desktop and mobile platforms may share all of the _Model_ layer, but their UX is almost certainly very different. It doesn't make much sense to try to share the _View Model_ layer between radically different UX implementations. The navigation logic should likewise be portable between mobile platforms or between desktop platforms, but probably not between both. My suggestion is to not try to share your _View Model_ component between desktop and mobile platforms, and this is just yet another reason for that.

Other Approaches and Extensions
=====

There are many other potential approaches to this kind of problem. Most are going to involve somehow communicating from the _View Model_ layer to the _View_ layer. In my case I used dependency injection directly, but another approach, outlined by Alec Tucker [on his blog](http://blog.alectucker.com/post/2014/07/26/using-messageingcenter-in-xamarin-forms-for-viewmodel-to-viewmodel-navigation.aspx), is to use the Xamarin.Forms `MessagingCenter` API to request the _View_ to perform a navigation. There are pros and cons to each approach so I'll let the reader make up his own mind about which he prefers.

This approach could also be extended to support more kinds of navigation and other platforms. I provided a Xamarin.Forms implementation as a reference, but it should be possible to create other implementations for other platforms.
